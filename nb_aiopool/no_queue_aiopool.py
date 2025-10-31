import asyncio
from typing import Awaitable, Optional, Set


class NoQueueAioPool:
    """
    NoQueueAioPool 是一个无队列的协程池，它通过一个条件变量来控制并发任务的数量。
    当任务数量达到最大并发数时，新提交的任务会被阻塞，直到有任务完成并释放空位。
    实测性能比 NoQueueAioPoolUseCondition 好，实现更简单。
    """
    def __init__(self, max_concurrency: int):
        self.max_concurrency = max_concurrency
        self.tasks: Set[asyncio.Task] = set()

    async def submit(self, coro: Awaitable, future: Optional[asyncio.Future] = None) -> asyncio.Future:
        """
        提交任务
        - coro: 要执行的协程
        - future: 外部传入 future，否则内部创建
        - 返回 future
        """
        # 如果没有传 future，就创建一个
        if future is None:
            future = asyncio.get_event_loop().create_future()

        async def wrapper():
            try:
                result = await coro
                if not future.done():
                    future.set_result(result)
            except Exception as e:
                if not future.done():
                    future.set_exception(e)

        # 背压：任务满时让出事件循环给 worker 执行
        while len(self.tasks) >= self.max_concurrency:
            await asyncio.sleep(0.01)

        task = asyncio.create_task(wrapper())
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

        return future

    async def run(self, coro: Awaitable,future: Optional[asyncio.Future] = None) :
        """
        提交任务，返回 Future
        :param coro: 协程对象
        :param future: 可选的外部 Future 对象
        :return: 协程执行结果
        """
        return await self.submit(coro, future=future)

    async def wait(self):
        """等待所有任务完成"""
        if self.tasks:
            await asyncio.gather(*self.tasks)


    async def __aenter__(self):
        await self._ensure_started()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.wait()



