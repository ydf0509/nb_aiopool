"""
```markdown
SmartAioPool - 智能异步线程池

一个高级异步IO线程池实现，具有以下核心特性：

## 主要功能
1. **动态工作线程管理**：根据任务负载自动增减工作线程数量
2. **任务队列管理**：支持最大队列大小限制，防止内存溢出
3. **自动资源清理**：程序退出时自动等待未完成任务
4. **灵活的任务提交方式**：支持阻塞/非阻塞提交、同步/异步获取结果

## 核心特性
- **自适应扩展**：当任务队列中有等待任务且未达到最大并发数时自动创建工作线程
- **空闲回收**：工作线程空闲超时后自动回收，保留最小工作线程数
- **背压控制**：支持队列满时的阻塞和非阻塞提交模式
- **优雅关闭**：支持等待所有任务完成后再关闭线程池
- **自动等待机制**：
  * atexit机制：程序退出时自动等待未完成任务
  * smart_run包装器：自动等待所有任务完成
  * async_wait_for_all方法：手动触发等待所有任务完成

## 使用示例

```python
# 基本用法
pool = SmartAioPool(max_concurrency=100, min_workers=2)

# 提交任务并等待结果
result = await pool.run(my_async_func, arg1, arg2)

# 提交任务获取Future
future = await pool.submit(my_async_func, arg1, arg2)
result = await future

# 使用上下文管理器（推荐）
async with SmartAioPool(max_concurrency=50) as pool:
    result = await pool.run(my_async_func, arg1)
    
# 忘记等待？没关系！启用auto_shutdown后会自动处理
pool = SmartAioPool(auto_shutdown=True)
await pool.submit(my_async_func, arg1)  # 不需要手动等待
# smart_run会自动等待所有任务完成
```

## 自动等待机制说明
1. **atexit机制**：当auto_shutdown=True时，在程序退出时自动创建新事件循环执行未完成任务
2. **smart_run包装器**：替代asyncio.run()，在主协程结束后自动等待所有池中任务完成
3. **手动等待**：调用async_wait_for_all()方法手动等待所有任务完成

注意：此类设计用于需要动态调整并发度的场景，如Web爬虫、API调用等IO密集型任务。
```
"""

import signal
import time
import logging
import asyncio
import weakref
import concurrent.futures
import sys
import atexit
import threading
from typing import Callable, Any, Coroutine, List, TypeVar, Optional

T = TypeVar("T")
logger = logging.getLogger(__name__)

# 全局注册表，跟踪所有活跃的pool实例（用于atexit清理）
_active_pools: weakref.WeakSet = weakref.WeakSet()

# atexit清理标记
_atexit_registered = False


def _python_exit():
    """
    在程序退出时自动等待所有pool的pending任务完成
    模仿 ThreadPoolExecutor 的自动等待机制
    
    注意：这个函数需要重新运行未完成的任务，因为原始的事件循环已经关闭
    """
    pools_with_tasks = [pool for pool in list(_active_pools) if len(pool._pending_tasks) > 0]
    
    if not pools_with_tasks:
        return
    
    print(f"🔧 atexit: 发现 {len(pools_with_tasks)} 个pool有未完成任务，自动等待...")
    
    # 创建新的事件循环（因为旧的已经关闭）
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # 重新启动所有pool并执行剩余任务
        async def wait_all():
            for pool in pools_with_tasks:
                pending_tasks = list(pool._pending_tasks.values())  # 复制任务列表
                if not pending_tasks:
                    continue
                
                print(f"  重新执行 pool {id(pool)} 的 {len(pending_tasks)} 个任务...")
                
                # 重新启动pool（因为在新循环中）
                pool._is_running = False
                pool._is_shutdown = False
                pool._queue = None
                pool._lock = None
                pool._workers.clear()
                pool._worker_busy.clear()
                pool._pending_futures.clear()
                pool._pending_tasks.clear()
                
                try:
                    # 重新初始化并启动
                    await pool._start()
                    
                    # 重新提交所有任务
                    futures = []
                    for func, args, kwargs in pending_tasks:
                        future = await pool.submit(func, *args, **kwargs)
                        futures.append(future)
                    
                    # 等待所有任务完成
                    await asyncio.gather(*futures, return_exceptions=True)
                    
                    # 关闭pool
                    await pool.shutdown(wait=True)
                    
                    print(f"  ✅ pool {id(pool)} 的 {len(pending_tasks)} 个任务已完成")
                except Exception as e:
                    print(f"  ❌ pool {id(pool)} 执行失败: {e}")
            
            print("✅ atexit: 所有任务已完成")
        
        loop.run_until_complete(wait_all())
    finally:
        try:
            loop.close()
        except:
            pass


class SmartAioPool:
    def __init__(
        self,
        max_concurrency: int = 100,
        max_queue_size: int = 1000,
        min_workers: int = 1,
        idle_timeout: float = 5.0,
        auto_shutdown: bool = True,  # 自动在程序退出前等待任务完成
    ):
        self._max_concurrency = max_concurrency
        self._min_workers = min_workers
        self._max_queue_size = max_queue_size
        self._queue: Optional[asyncio.Queue] = None  # 延迟初始化
        self._workers: List[asyncio.Task] = []
        self._worker_busy: dict[asyncio.Task, bool] = {}  # True: busy, False: idle
        self._is_running = False
        self._is_shutdown = False
        self._lock: Optional[asyncio.Lock] = None  # 延迟初始化
        self._idle_timeout = idle_timeout
        self._auto_shutdown = auto_shutdown
        
        # 跟踪所有提交的future，用于自动等待
        self._pending_futures: set[asyncio.Future] = set()
        
        # 用于atexit：保存待执行的任务（因为future会失效）
        # 使用dict以获得O(1)的删除性能
        self._pending_tasks: dict[int, tuple] = {}  # {id(future): (func, args, kwargs), ...}
        
        self._background_task: Optional[asyncio.Task] = None
        
        # 注册到全局池并注册atexit（只注册一次）
        if self._auto_shutdown:
            _active_pools.add(self)
            self._register_atexit()

    def _register_atexit(self):
        """注册atexit清理函数（全局只注册一次）"""
        global _atexit_registered
        if not _atexit_registered:
            atexit.register(_python_exit)
            _atexit_registered = True
            logger.debug("✅ 已注册 atexit 自动清理")

    def _ensure_initialized(self):
        """确保在事件循环中初始化asyncio对象"""
        if self._queue is None:
            self._queue = asyncio.Queue(maxsize=self._max_queue_size)
        if self._lock is None:
            self._lock = asyncio.Lock()
    
    async def _start(self):
        self._ensure_initialized()
        async with self._lock:
            if self._is_running:
                return
            self._is_running = True
            for _ in range(self._min_workers):
                self._create_worker()

    async def _worker(self):
        task = asyncio.current_task()
        while True:
            if self._is_shutdown and self._queue.empty():
                break
            try:
                item = await asyncio.wait_for(
                    self._queue.get(), timeout=self._idle_timeout
                )
            except asyncio.TimeoutError:
                # 空闲超时，若当前 Worker 超过最小 Worker 数量，则退出
                async with self._lock:
                    if len(self._workers) > self._min_workers:
                        break
                continue

            func, args, kwargs, fut = item
            self._worker_busy[task] = True
            try:
                result = await func(*args, **kwargs)
                if fut and not fut.cancelled():
                    fut.set_result(result)
            except Exception as e:
                if fut and not fut.cancelled():
                    fut.set_exception(e)
            finally:
                self._queue.task_done()
                self._worker_busy[task] = False

        # Worker退出，清理
        async with self._lock:
            if task in self._workers:
                self._workers.remove(task)
                self._worker_busy.pop(task, None)

    def _create_worker(self):
        """在锁的保护下创建worker"""
        task = asyncio.create_task(self._worker())
        self._workers.append(task)
        self._worker_busy[task] = False
        return task

    async def _maybe_add_worker(self):
        self._ensure_initialized()
        async with self._lock:
            if len(self._workers) >= self._max_concurrency:
                return
            idle_workers = sum(1 for busy in self._worker_busy.values() if not busy)
            queue_size = self._queue.qsize()
            if queue_size > idle_workers and len(self._workers) < self._max_concurrency:
                task = self._create_worker()
                logger.debug(f'create worker {id(task)}, queue_size={queue_size}, idle_workers={idle_workers}, total_workers={len(self._workers)}')

    async def submit(
        self,
        func: Callable[..., Coroutine[Any, Any, T]],
        *args,
        block: bool = True,
        future: Optional[asyncio.Future] = None,
        **kwargs
    ) -> asyncio.Future:
        if self._is_shutdown:
            raise RuntimeError("Pool is shutdown, cannot submit new tasks.")

        if not self._is_running:
            await self._start()

        if future is None:
            future = asyncio.get_running_loop().create_future()

        # 保存任务信息（用于atexit重新执行）
        # 使用future的id作为key，避免O(n)的list.remove()操作
        future_id = id(future)
        task_info = (func, args, kwargs)
        self._pending_tasks[future_id] = task_info

        # 跟踪future，自动清理已完成的
        self._pending_futures.add(future)
        
        def on_done(f):
            self._pending_futures.discard(f)
            # 任务完成后从pending_tasks中移除（O(1)操作）
            self._pending_tasks.pop(id(f), None)
        
        future.add_done_callback(on_done)

        try:
            if block:
                await self._queue.put((func, args, kwargs, future))
            else:
                self._queue.put_nowait((func, args, kwargs, future))
        except asyncio.QueueFull:
            future.set_exception(RuntimeError("Queue full"))

        # 尝试增加 Worker
        await self._maybe_add_worker()
        return future

    async def run(
        self,
        func: Callable[..., Coroutine[Any, Any, T]],
        *args,
        block: bool = True,
        future: Optional[asyncio.Future] = None,
        **kwargs
    ) -> T:
        fut = await self.submit(func, *args, block=block, future=future, **kwargs)
        return await fut

    def sync_submit(
        self,
        func: Callable[..., Coroutine[Any, Any, T]],
        *args,
        block: bool = True,
        future: Optional[asyncio.Future] = None,
        loop: Optional[asyncio.AbstractEventLoop] = None,
        **kwargs
    ) -> concurrent.futures.Future:
        if loop is None:
            raise ValueError("please pass loop")
        return asyncio.run_coroutine_threadsafe(
            self.submit(func, *args, block=block, future=future, **kwargs), loop
        )

    async def shutdown(self, wait: bool = True):
        self._ensure_initialized()
        async with self._lock:
            if self._is_shutdown:
                return
            self._is_shutdown = True

        if wait:
            await self._queue.join()
            
            # 只等待还未完成的worker
            active_workers = [w for w in self._workers if not w.done()]
            if active_workers:
                try:
                    await asyncio.gather(*active_workers, return_exceptions=True)
                except RuntimeError as e:
                    # 事件循环已关闭，忽略
                    if 'Event loop is closed' not in str(e):
                        raise

        async with self._lock:
            self._workers.clear()
            self._worker_busy.clear()
            self._pending_futures.clear()
            self._is_running = False

    async def __aenter__(self):
        await self._start()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.shutdown(wait=True)
    
    async def async_wait_for_all(self) -> None:
        """异步方法：等待所有pending的任务完成"""
        if self._pending_futures:
            logger.info(f"Waiting for {len(self._pending_futures)} pending tasks...")
            await asyncio.gather(*list(self._pending_futures), return_exceptions=True)
            logger.info("All tasks completed.")
    
    @property
    def pending_count(self) -> int:
        """返回当前未完成的任务数量"""
        return len(self._pending_futures)
    
    @property
    def worker_count(self) -> int:
        """返回当前worker数量"""
        return len(self._workers)
    
    @property
    def busy_worker_count(self) -> int:
        """返回繁忙的worker数量"""
        return sum(1 for busy in self._worker_busy.values() if busy)
    
    @property
    def idle_worker_count(self) -> int:
        """返回空闲的worker数量"""
        return sum(1 for busy in self._worker_busy.values() if not busy)
    
    def __repr__(self) -> str:
        """返回pool的字符串表示"""
        return (
            f"SmartAioPool("
            f"workers={len(self._workers)}, "
            f"busy={self.busy_worker_count}, "
            f"pending={len(self._pending_futures)}, "
            f"max={self._max_concurrency}, "
            f"running={self._is_running})"
        )
    
    async def cancel_all(self):
        """取消所有pending的任务"""
        cancelled_count = 0
        for future in list(self._pending_futures):
            if not future.done():
                future.cancel()
                cancelled_count += 1
        self._pending_futures.clear()
        logger.info(f"Cancelled {cancelled_count} pending tasks.")
        return cancelled_count


# ======================
# 智能 asyncio.run 包装器
# ======================

def smart_run(coro, *, debug=False):
    """
    智能的 asyncio.run 包装器，自动等待所有pool的pending任务完成
    
    用法:
        pool = SmartAioPool(auto_shutdown=True)
        
        async def main():
            await pool.submit(task, 1)
            # 不需要手动等待！
        
        smart_run(main())  # 自动等待所有pending任务
    """
    async def wrapper():
        try:
            # 执行用户的主协程
            result = await coro
            
            # 自动等待所有活跃pool的pending任务
            for pool in list(_active_pools):
                if pool.pending_count > 0:
                    logger.info(f"🔧 Auto-waiting for {pool.pending_count} pending tasks in pool...")
                    await pool.async_wait_for_all()
            
            return result
        except Exception as e:
            # 即使出错也要等待pending任务
            for pool in list(_active_pools):
                if pool.pending_count > 0:
                    logger.warning(f"⚠️  Exception occurred, but still waiting for {pool.pending_count} pending tasks...")
                    await pool.async_wait_for_all()
            raise
    
    return asyncio.run(wrapper(), debug=debug)


if __name__ == "__main__":
    # ======================
    # 示例用法
    # ======================

    async def sample_task(x: int):
        await asyncio.sleep(0.1)
        print(time.strftime("%H:%M:%S"),x,id(asyncio.current_task()))
        return x * 2
    
    # ========= 测试1：传统方式（手动await） =========
    print("="*50)
    print("测试1：手动await future")
    print("="*50)
    pool1 = SmartAioPool(max_concurrency=100, max_queue_size=1000, min_workers=2)
    async def test_manual_await():
        future = await pool1.submit(sample_task, 1)
        result = await future
        print(f"✅ Task result: {result}")
        await pool1.shutdown(wait=True)
    
    asyncio.run(test_manual_await())
    
    # ========= 测试2：智能模式（忘记await，自动等待） =========
    print("\n" + "="*50)
    print("测试2：忘记await future，但启用auto_shutdown")
    print("="*50)
    pool2 = SmartAioPool(max_concurrency=100, min_workers=0, auto_shutdown=True)
    async def test_auto_wait():
        # 故意不await future，模拟用户忘记等待
        await pool2.submit(sample_task, 10)
        await pool2.submit(sample_task, 11)
        await pool2.submit(sample_task, 12)
        print(f"📊 提交了3个任务，pending count: {pool2.pending_count}")
        
        # 用户可以主动调用等待
        await pool2.async_wait_for_all()
        print(f"✅ 所有任务完成！pending count: {pool2.pending_count}")
    
    asyncio.run(test_auto_wait())
    
    # ========= 测试3：使用 smart_run (完全自动) =========
    print("\n" + "="*50)
    print("测试3：使用 smart_run - 完全不需要手动等待！")
    print("="*50)
    pool3 = SmartAioPool(max_concurrency=100, min_workers=0, auto_shutdown=True)
    async def test_smart_run():
        # 只提交，啥都不管！
        await pool3.submit(sample_task, 30)
        await pool3.submit(sample_task, 31)
        await pool3.submit(sample_task, 32)
        print(f"📊 提交了3个任务，pending count: {pool3.pending_count}")
        print("✨ 用户不需要等待，smart_run会自动处理！")
        # 直接退出，不用await，不用shutdown
    
    smart_run(test_smart_run())  # 使用 smart_run 而不是 asyncio.run
    
    # ========= 测试4：普通 asyncio.run + atexit 自动等待 =========
    print("\n" + "="*50)
    print("测试4：普通 asyncio.run + atexit 自动等待！")
    print("="*50)
    print("💡 模仿 ThreadPoolExecutor 的 atexit 机制")
    print()
    
    pool4 = SmartAioPool(max_concurrency=100, min_workers=0, auto_shutdown=True)
    async def test_atexit_magic():
        await pool4.submit(sample_task, 40)
        await pool4.submit(sample_task, 41)
        await pool4.submit(sample_task, 42)
        print(f"📊 提交了3个任务，pending count: {pool4.pending_count}")
        print("✨ 直接退出，不手动等待...")
        print("✨ atexit 会自动等待所有任务完成！")
        # 不等待，直接退出
    
    asyncio.run(test_atexit_magic())
    print(f"📊 asyncio.run 退出后，pending count: {pool4.pending_count}")
    print("⏳ 等待程序退出时的 atexit 清理...")
    # atexit 会在这里自动运行！

