import asyncio
from typing import Awaitable, Optional, Set


class NoQueueAioPoolUseCondition:
    def __init__(self, max_concurrency: int):
        self.max_concurrency = max_concurrency
        self.tasks: Set[asyncio.Task] = set()
        self._condition = asyncio.Condition()  # 条件变量：自带锁 + 等待/通知机制

    async def submit(self, coro: Awaitable, future: Optional[asyncio.Future] = None) -> asyncio.Future:
        """
        提交任务
        :param coro: 协程对象
        :param future: 可选外部 Future
        :return: asyncio.Future
        """
        if future is None:
            future = asyncio.get_running_loop().create_future()

        async def wrapper():
            try:
                result = await coro
                if not future.done():
                    future.set_result(result)
            except Exception as e:
                if not future.done():
                    future.set_exception(e)

        # 使用条件变量保护临界区
        async with self._condition:
            # 背压：任务满时等待有空位
            while len(self.tasks) >= self.max_concurrency:
                await self._condition.wait()  # 自动释放锁并等待通知
            
            # 创建并添加任务
            task = asyncio.create_task(wrapper())
            self.tasks.add(task)
            
            # 任务完成回调
            def _on_done(t):
                async def cleanup():
                    async with self._condition:
                        self.tasks.discard(t)
                        # 通知一个等待的协程
                        self._condition.notify()
                
                asyncio.create_task(cleanup())
            
            task.add_done_callback(_on_done)

        return future

    async def run(self, coro: Awaitable, future: Optional[asyncio.Future] = None):
        """提交任务并等待结果"""
        fut = await self.submit(coro, future=future)
        return await fut

    async def wait(self):
        """等待所有任务完成"""
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
