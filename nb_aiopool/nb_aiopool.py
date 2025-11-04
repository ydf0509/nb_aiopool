import concurrent.futures

import asyncio
from typing import Any, Coroutine, List, TypeVar

T = TypeVar("T")  # 用于标注异步函数返回类型


class NbAioPool:
    """
    NbAioPool 是一个经典的基于 `asyncio.Queue`有界队列 的并发池。
    它通过固定数量的后台工作协程（worker）来消费队列中的任务，实现稳定可靠的并发控制。
    """
    def __init__(self, max_concurrency: int = 100, max_queue_size: int = 1000):
        self._max_concurrency = max_concurrency
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size)
        self._workers: List[asyncio.Task] = []
        self._running = False
        self._stopped = False
        self._lock = asyncio.Lock()
   

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




