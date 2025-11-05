"""
nb_aio_task - 基于 Redis + NbAioPool 的简易分布式异步任务队列

特点：
- 简单：无需复杂配置，装饰器即用
- 高效：利用 NbAioPool 的背压机制和并发控制
- 分布式：基于 Redis 实现任务队列
"""

import asyncio
import json
import pickle
import traceback
from typing import Callable, Any, List, Optional
from functools import wraps

try:
    import redis.asyncio as aioredis
except ImportError:
    try:
        import aioredis
    except ImportError:
        raise ImportError(
            "请安装 redis 依赖: pip install redis[asyncio] 或 pip install aioredis"
        )

from nb_aiopool.nb_aiopool import NbAioPool


class AioTask:
    """异步任务包装器"""
    
    def __init__(
        self,
        func: Callable,
        queue_name: str,
        max_concurrency: int = 100,
        redis_url: str = "redis://localhost:6379/0",
        max_queue_size: int = 100, # NbAioPool 的 asyncio.Queue 内存工作队列大小，不是指redis list的最大长度限制。
        use_pickle: bool = True,
    ):
        """
        初始化异步任务
        
        :param func: 被装饰的异步函数
        :param queue_name: Redis 队列名称
        :param max_concurrency: 最大并发数
        :param redis_url: Redis 连接URL
        :param max_queue_size: NbAioPool 队列大小
        :param use_pickle: 是否使用 pickle 序列化（支持复杂对象），否则使用 json
        """
        self.func = func
        self.queue_name = f"nb_aio_task:{queue_name}"
        self.max_concurrency = max_concurrency
        self.redis_url = redis_url
        self.max_queue_size = max_queue_size
        self.use_pickle = use_pickle
        
        self._redis: Optional[aioredis.Redis] = None
        self._pool: Optional[NbAioPool] = None
        self._consuming = False
        
        # 保留原函数的元信息
        wraps(func)(self)

    async def __call__(self, *args, **kwargs) -> Any:
        """直接运行函数"""
        return await self.func(*args, **kwargs)
    
    async def _get_redis(self) -> aioredis.Redis:
        """获取 Redis 连接（单例）"""
        if self._redis is None:
            self._redis = await aioredis.from_url(
                self.redis_url,
                decode_responses=False  # 使用 bytes 模式以支持 pickle
            )
        return self._redis
    
    def _serialize(self, data: Any) -> bytes:
        """序列化数据"""
        if self.use_pickle:
            return pickle.dumps(data)
        else:
            return json.dumps(data).encode('utf-8')
    
    def _deserialize(self, data: bytes) -> Any:
        """反序列化数据"""
        if self.use_pickle:
            return pickle.loads(data)
        else:
            return json.loads(data.decode('utf-8'))
    
    async def submit(self, *args, **kwargs) -> None:
        """
        提交任务到 Redis 队列
        
        :param args: 函数位置参数
        :param kwargs: 函数关键字参数
        """
        redis = await self._get_redis()
        task_data = {
            'args': args,
            'kwargs': kwargs,
        }
        serialized = self._serialize(task_data)
        await redis.rpush(self.queue_name, serialized)
        print(f"✅ 任务已提交到队列 {self.queue_name}: {self.func.__name__}({args}, {kwargs})")
    
    async def _execute_task(self, task_data: bytes) -> Any:
        """执行单个任务"""
        try:
            data = self._deserialize(task_data)
            args = data.get('args', ())
            kwargs = data.get('kwargs', {})
            
            result = await self.func(*args, **kwargs)
            print(f"✅ 任务执行成功: {self.func.__name__}({args}, {kwargs}) -> {result}")
            return result
        
        except Exception as e:
            print(f"❌ 任务执行失败: {self.func.__name__}")
            print(f"   错误: {e}")
            traceback.print_exc()
            raise
    
    async def consume(self, timeout: int = 5) -> None:
        """
        启动消费者，持续从 Redis 队列消费任务
        
        :param timeout: 每次 blpop 的超时时间（秒）
        """
        if self._consuming:
            print(f"⚠️  消费者已在运行: {self.queue_name}")
            return
        
        self._consuming = True
        redis = await self._get_redis()
        
        # 创建 NbAioPool
        self._pool = NbAioPool(
            max_concurrency=self.max_concurrency,
            max_queue_size=self.max_queue_size
        )
        
        print(f"🚀 启动消费者: {self.queue_name} (并发数: {self.max_concurrency})")
        
        try:
            while self._consuming:
                # 阻塞式获取任务
                result = await redis.blpop(self.queue_name, timeout=timeout)
                
                if result is None:
                    # 超时，继续循环
                    await asyncio.sleep(0.1)
                    continue
                
                _, task_data = result
                
                # 提交到 NbAioPool 执行（利用背压机制）
                await self._pool.submit(self._execute_task(task_data))
        
        except asyncio.CancelledError:
            print(f"🛑 消费者被取消: {self.queue_name}")
        
        except Exception as e:
            print(f"❌ 消费者异常退出: {self.queue_name}")
            print(f"   错误: {e}")
            traceback.print_exc()
        
        finally:
            # 清理资源
            if self._pool:
                await self._pool.shutdown(wait=True)
            print(f"🛑 消费者已停止: {self.queue_name}")
    
    async def stop(self) -> None:
        """停止消费者"""
        self._consuming = False
        print(f"正在停止消费者: {self.queue_name}")
    
    async def get_queue_size(self) -> int:
        """获取队列中待处理任务数量"""
        redis = await self._get_redis()
        return await redis.llen(self.queue_name)
    
    async def clear_queue(self) -> None:
        """清空队列"""
        redis = await self._get_redis()
        await redis.delete(self.queue_name)
        print(f"🗑️  队列已清空: {self.queue_name}")
    
    async def close(self) -> None:
        """关闭 Redis 连接"""
        if self._redis:
            await self._redis.close()
            self._redis = None


def aio_task(
    queue_name: str,
    max_concurrency: int = 50,
    redis_url: str = "redis://localhost:6379/0",
    max_queue_size: int = 1000,
    use_pickle: bool = True,
):
    """
    异步任务装饰器
    
    使用示例：
    
    ```python
    @aio_task(queue_name="my_queue", max_concurrency=100)
    async def my_task(x, y):
        await asyncio.sleep(1)
        return x + y
    
    # 提交任务
    await my_task.submit(1, 2)
    
    # 启动消费者
    await my_task.consume()
    ```
    
    :param queue_name: Redis 队列名称
    :param max_concurrency: 最大并发数
    :param redis_url: Redis 连接URL
    :param max_queue_size: NbAioPool 队列大小
    :param use_pickle: 是否使用 pickle 序列化
    """
    def decorator(func: Callable) -> AioTask:
        if not asyncio.iscoroutinefunction(func):
            raise TypeError(f"{func.__name__} 必须是异步函数 (async def)")
        
        return AioTask(
            func=func,
            queue_name=queue_name,
            max_concurrency=max_concurrency,
            redis_url=redis_url,
            max_queue_size=max_queue_size,
            use_pickle=use_pickle,
        )
    
    return decorator


async def batch_consume(
    tasks: List[AioTask],
    timeout: int = 5
) -> None:
    """
    批量启动多个任务的消费者
    
    :param tasks: AioTask 列表
    :param timeout: 每次 blpop 的超时时间（秒）
    
    使用示例：
    
    ```python
    await batch_consume([my_task1, my_task2, my_task3])
    ```
    """
    print(f"🚀 批量启动 {len(tasks)} 个消费者")
    
    # 并发启动所有消费者
    await asyncio.gather(
        *[task.consume(timeout=timeout) for task in tasks],
        return_exceptions=True
    )


# ==================== 示例代码 ====================

if __name__ == "__main__":
    
    @aio_task(queue_name="test_queue1", max_concurrency=10)
    async def add_task(x, y):
        """测试任务：加法"""
        await asyncio.sleep(0.5)
        result = x + y
        print(f"计算结果: {x} + {y} = {result}")
        return result
    
    @aio_task(queue_name="test_queue2", max_concurrency=5)
    async def multiply_task(a, b):
        """测试任务：乘法"""
        await asyncio.sleep(1)
        result = a * b
        print(f"计算结果: {a} * {b} = {result}")
        return result
    
    async def producer():
        """生产者：提交任务"""
        print("\n" + "="*60)
        print("生产者启动：开始提交任务")
        print("="*60)
        
        # 提交 20 个加法任务
        for i in range(20):
            await add_task.submit(i, i+1)
        
        # 提交 10 个乘法任务
        for i in range(10):
            await multiply_task.submit(i, 2)
        
        print(f"\n队列状态:")
        print(f"  add_task 队列: {await add_task.get_queue_size()} 个任务")
        print(f"  multiply_task 队列: {await multiply_task.get_queue_size()} 个任务")
    
    async def consumer():
        """消费者：处理任务"""
        print("\n" + "="*60)
        print("消费者启动：开始处理任务")
        print("="*60)
        
        # 方式1：单独启动消费者
        # await add_task.consume()
        
        # 方式2：批量启动消费者 ⭐ 推荐
        await batch_consume([add_task, multiply_task])
    
    async def main():
        """主函数"""
        # 直接运行函数
        print(f"直接运行函数: {await add_task(1,2)}")

        # 先提交任务
        await producer()
        
        # 等待一下，让任务进入队列
        await asyncio.sleep(1)
        
        # 启动消费者（这会阻塞运行）
        await consumer()
    
    # 运行示例
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║  nb_aio_task - 简易分布式异步任务队列示例                ║
    ║                                                          ║
    ║  提示：请先启动 Redis 服务                                ║
    ║  $ redis-server                                          ║
    ╚══════════════════════════════════════════════════════════╝
    """)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 程序已停止")
