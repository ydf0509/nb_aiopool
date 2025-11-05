
import asyncio
from nb_aiopool.contrib.nb_aio_task import aio_task, batch_consume

@aio_task(queue_name="my_queue1", max_concurrency=100)
async def my_fun1(x, y):
    await asyncio.sleep(1)
    print(f"my_fun1: {x}, {y}")
    for i in range(5): # 消费函数可以继续向其他队列中发消息
        await my_fun2.submit(a=x*3 + i)
    return x + y

@aio_task(queue_name="my_queue2", max_concurrency=50)
async def my_fun2(a):
    await asyncio.sleep(1)
    print(f"my_fun2: {a}")
    return a * 2

async def producer():
    # 提交任务到 Redis 队列
    await my_fun1.submit(1, 2)
    await my_fun1.submit(10, 20)
    await my_fun1.submit(100, 200)
    # 查看队列大小
    print(f"队列大小: {await my_fun1.get_queue_size()}")


### 3. 消费任务（消费者）
async def consumer():
    

    # 方式1：单独启动消费者
    # await my_fun1.consume()
    
    # 方式2：批量启动多个消费者 ⭐ 推荐
    await batch_consume([my_fun1, my_fun2])


### 4. 完整示例
async def main():
    # 任然可以直接运行函数，但不会进入队列
    print(f"直接运行函数: {await my_fun1(1,2)}")

    # 提交任务
    for i in range(100):
        await my_fun1.submit(i, i+1)
    
    # 启动消费者（阻塞运行）
    await batch_consume([my_fun1, my_fun2])

if __name__ == "__main__":
    # 方式1：使用 asyncio.run（任务执行完会退出）

    asyncio.run(main())