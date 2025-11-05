# nb_aio_task - 简易分布式异步任务队列

基于 **Redis + NbAioPool** 实现的轻量级分布式异步任务队列，类似 RQ/Celery/Funboost，但更简单。

## 特点

- ✅ **简单易用**：装饰器即用，无需复杂配置
- ✅ **高效稳定**：充分利用 `NbAioPool` 的背压机制和并发控制
- ✅ **分布式**：基于 Redis 实现任务队列，支持多进程/多机器消费
- ✅ **类型支持**：支持 pickle/json 序列化，可传递复杂对象

## 安装依赖

```bash
pip install redis  # 或 pip install aioredis
```

## 快速开始

### 1. 定义任务

```python
import asyncio
from nb_aiopool.contrib import aio_task, batch_consume

@aio_task(queue_name="my_queue1", max_concurrency=100)
async def my_fun1(x, y):
    await asyncio.sleep(1)
    print(f"my_fun1: {x}, {y}")
    return x + y

@aio_task(queue_name="my_queue2", max_concurrency=50)
async def my_fun2(a):
    await asyncio.sleep(1)
    print(f"my_fun2: {a}")
    return a * 2
```

### 2. 提交任务（生产者）

```python
async def producer():
    # 提交任务到 Redis 队列
    await my_fun1.submit(1, 2)
    await my_fun1.submit(10, 20)
    await my_fun2.submit(3)
    
    # 查看队列大小
    print(f"队列大小: {await my_fun1.get_queue_size()}")
```

### 3. 消费任务（消费者）

```python
async def consumer():
    # 任然可以直接运行函数，但不会进入队列
    print(f"直接运行函数: {await my_fun1(1,2)}")

    # 方式1：单独启动消费者
    await my_fun1.consume()
    
    # 方式2：批量启动多个消费者 ⭐ 推荐
    await batch_consume([my_fun1, my_fun2])
```

### 4. 完整示例

```python
async def main():
    # 提交任务
    for i in range(100):
        await my_fun1.submit(i, i+1)
    
    # 启动消费者（阻塞运行）
    await batch_consume([my_fun1, my_fun2])

if __name__ == "__main__":
    # 方式1：使用 asyncio.run（任务执行完会退出）
    asyncio.run(main())
    
    # 方式2：使用 loop.run_forever（持续运行）
    # loop = asyncio.get_event_loop()
    # loop.create_task(main())
    # loop.run_forever()
```

## API 参考

### `@aio_task` 装饰器

```python
@aio_task(
    queue_name: str,              # Redis 队列名称（必填）
    max_concurrency: int = 50,    # 最大并发数
    redis_url: str = "redis://localhost:6379/0",  # Redis 连接URL
    max_queue_size: int = 1000,   # NbAioPool 队列大小
    use_pickle: bool = True,      # 是否使用 pickle 序列化
)
```

### 任务方法

```python
# 提交任务到队列
await my_task.submit(*args, **kwargs)

# 启动消费者
await my_task.consume(timeout=5)

# 停止消费者
await my_task.stop()

# 获取队列大小
size = await my_task.get_queue_size()

# 清空队列
await my_task.clear_queue()

# 关闭 Redis 连接
await my_task.close()
```

### 批量启动消费者

```python
from nb_aiopool.contrib import batch_consume

# 同时启动多个任务的消费者
await batch_consume([task1, task2, task3], timeout=5)
```

## 高级用法

### 1. 处理复杂对象

```python
@aio_task(queue_name="complex_queue", use_pickle=True)
async def process_data(data: dict):
    # 使用 pickle 可以传递任意 Python 对象
    name = data['name']
    items = data['items']
    return f"Processed {len(items)} items for {name}"

await process_data.submit({
    'name': 'User-A',
    'items': [1, 2, 3, 4, 5]
})
```

### 2. 生产者-消费者分离

**生产者进程（producer.py）：**
```python
import asyncio
from nb_aiopool.contrib import aio_task

@aio_task(queue_name="tasks", max_concurrency=50)
async def my_task(x):
    return x * 2

async def main():
    # 持续提交任务
    for i in range(1000):
        await my_task.submit(i)
        await asyncio.sleep(0.1)

asyncio.run(main())
```

**消费者进程（consumer.py）：**
```python
import asyncio
from nb_aiopool.contrib import aio_task

@aio_task(queue_name="tasks", max_concurrency=50)
async def my_task(x):
    await asyncio.sleep(1)
    print(f"处理任务: {x}")
    return x * 2

async def main():
    # 持续消费任务
    await my_task.consume()

asyncio.run(main())
```

### 3. 多机器部署

只需要多个机器连接同一个 Redis，使用相同的 `queue_name`：

```python
# 机器1：生产者
@aio_task(queue_name="shared_queue", redis_url="redis://192.168.1.100:6379/0")
async def task(x):
    return x * 2

# 机器2：消费者
@aio_task(queue_name="shared_queue", redis_url="redis://192.168.1.100:6379/0")
async def task(x):
    return x * 2

# 机器1 提交任务
await task.submit(100)

# 机器2 消费任务
await task.consume()
```

## 对比其他框架

| 特性 | nb_aio_task | Celery | RQ | Funboost |
|------|-------------|--------|-----|----------|
| 复杂度 | ⭐ 极简 | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ |
| 异步支持 | ✅ 原生 | ⚠️ 需配置 | ❌ | ✅ |
| 并发控制 | ✅ 内置 | ⚠️ 有限 | ⚠️ 有限 | ✅ |
| 依赖 | Redis | RabbitMQ/Redis | Redis | 多种 |
| 学习曲线 | 5分钟 | 1天 | 30分钟 | 2小时 |

## 注意事项

1. **Redis 必须运行**：确保 Redis 服务已启动
2. **队列持久化**：Redis 数据会持久化，重启后任务不丢失
3. **错误处理**：任务执行失败会打印异常，但不会重试（保持简单）
4. **序列化选择**：
   - `use_pickle=True`：支持复杂对象，但不安全（不要处理不信任的数据）
   - `use_pickle=False`：只支持 JSON 可序列化的对象，但更安全

## 运行示例

```bash
# 1. 启动 Redis
redis-server

# 2. 运行示例
python -m nb_aiopool.contrib.example

# 3. 或运行内置测试
python -m nb_aiopool.contrib.nb_aio_task
```

## 许可证

MIT
