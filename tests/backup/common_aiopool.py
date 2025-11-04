import concurrent.futures
import weakref
import asyncio
from typing import Any, Coroutine, List, TypeVar

T = TypeVar("T")  # 用于标注异步函数返回类型

_active_pools = weakref.WeakSet()

class CommonAioPool:
    """
    CommonAioPool 是一个经典的基于 `asyncio.Queue`有界队列 的并发池。
    它通过固定数量的后台工作协程（worker）来消费队列中的任务，实现稳定可靠的并发控制。
    它的实现简单，性能良好，是许多场景下的首选。
    """
    def __init__(self, max_concurrency: int = 100, max_queue_size: int = 1000):
        self._max_concurrency = max_concurrency
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size)
        self._workers: List[asyncio.Task] = []
        self._running = False
        self._stopped = False
        self._lock = asyncio.Lock()
        _active_pools.add(self)

    async def _worker(self):
        while True:
            coro, fut = await self._queue.get()
            if coro is None:
                # 哨兵，退出 worker
                self._queue.task_done()
                break
            try:
                result = await coro
                if not fut.cancelled():
                    fut.set_result(result)
            except Exception as e:
                if not fut.cancelled():
                    fut.set_exception(e)
            finally:
                self._queue.task_done()

    async def _ensure_started(self):
        async with self._lock:
            if not self._running:
                self._workers = [asyncio.create_task(self._worker()) for _ in range(self._max_concurrency)]
                self._running = True



    async def submit(self,
                     coro: Coroutine[Any, Any, T],
                     block: bool = True,
                     future: asyncio.Future = None) -> asyncio.Future:
        """
        提交任务，返回 Future
        :param coro: 协程对象
        :param block: True 队列满等待，False 队列满立即抛异常
        :param future: 可选的外部 Future 对象
        """
        if self._stopped:
            raise RuntimeError("Pool is stopped, cannot submit new tasks.")

        await self._ensure_started()
        if future is None:
            future = asyncio.get_running_loop().create_future()
        try:
            if block:
                await self._queue.put((coro, future))
            else:
                self._queue.put_nowait((coro, future))
        except asyncio.QueueFull:
            future.set_exception(RuntimeError("Queue full"))
        return future

    async def run(self,
                     coro: Coroutine[Any, Any, T],
                     block: bool = True,
                     future: asyncio.Future = None) -> T:
        """
        await pool.run 相当于 await await pool.submit

        :param coro: 协程对象
        :param block: True 队列满等待，False 队列满立即抛异常
        :param future: 可选的外部 Future 对象
        :return: 协程执行结果
        """
        future: asyncio.Future = await self.submit(coro, block=block, future=future)
        return await future

    def sync_submit(self,
                     coro: Coroutine[Any, Any, T],
                     block: bool = True,
                     future: asyncio.Future = None,
                     loop: asyncio.AbstractEventLoop = None) -> concurrent.futures.Future:
        """
        同步提交任务，返回 concurrent.futures.Future
        :param coro: 协程对象
        :param block: True 队列满等待，False 队列满立即抛异常
        :param future: 可选的外部 Future 对象
        :param loop: 事件循环对象
        """
        if loop is None:
            raise ValueError("please pass loop")
        return asyncio.run_coroutine_threadsafe(
            self.submit(coro, block=block, future=future), loop)


    async def shutdown(self, wait: bool = True):
        """
        优雅关闭池
        :param wait: True 等待任务完成并 worker 退出，False 仅发哨兵后台退出
        """
        self._stopped = True

        if wait:
            # 等待队列中所有任务完成
            await self._queue.join()

        # 发送哨兵，确保所有 worker 能退出
        for _ in range(self._max_concurrency):
            await self._queue.put((None, None))

        if wait:
            # 等待所有 worker 完全退出
            await asyncio.gather(*self._workers, return_exceptions=True)

        # 清理状态
        self._workers.clear()
        self._running = False

    # =================
    # Async Context Manager
    # =================
    async def __aenter__(self):
        await self._ensure_started()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.shutdown(wait=True)

async def shutdown_all_common_aiopools():
    for pool in _active_pools:
        await pool.shutdown(wait=True)
    _active_pools.clear()


if __name__ == '__main__':

    # ======================
    # 示例用法
    # ======================

    async def sample_task(x: int):
        await asyncio.sleep(0.1)
        print(x)
        return x * 2

    async def main1():
        pool = CommonAioPool(max_concurrency=10, max_queue_size=1000)
        # 提交任务（现在使用协程对象）
        futures = [await pool.submit(sample_task(i)) for i in range(100)]

        # 等待任务完成
        results = await asyncio.gather(*futures)
        print("结果:", results)


    async def main2():
        async with CommonAioPool(max_concurrency=10, max_queue_size=1000) as pool:
            for i in range(100):
                await pool.submit(sample_task(i))  # 这样不阻塞当前for循环，是丢到queue队列后不管
                await (await pool.submit(sample_task(i)))  # 这样是直接得到异步函数的执行结果，阻塞当前for循环
                await pool.run(sample_task(i))  # 和上面 await (await pool.submit(sample_task(i))) 等价。


    async def not_block_main():
        pool = CommonAioPool(max_concurrency=10, max_queue_size=1000)
        pool2 = CommonAioPool(max_concurrency=20, max_queue_size=1000)
        for i in range(100):
            await pool2.submit(sample_task(i))
            await pool.submit(sample_task(i))
        # await pool.shutdown(wait=True)  # 如果不用async with创建pool，  忘了写这个shutdown就悲催了，程序提前退出
        await shutdown_all_common_aiopools()

    asyncio.run(not_block_main())
