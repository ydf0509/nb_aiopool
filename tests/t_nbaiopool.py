import asyncio
from nb_aiopool import NbAioPool

async def sample_task(x: int):
    await asyncio.sleep(0.1)
    print(x)
    return x * 2

async def main1():
    pool = NbAioPool(max_concurrency=10, max_queue_size=1000)
    # 提交任务（现在使用协程对象）
    futures = [await pool.submit(sample_task(i)) for i in range(100)]

    # 等待任务完成,打印完成,你也可以不等待，因为你只要写了 pool.shutdown(wait=True) 兜底，就不会造成代码提前结束退出。
    results = await asyncio.gather(*futures)
    print("结果:", results)
    pool.shutdown(wait=True) # 如果不用async with创建pool，你需要手动调用 pool.shutdown(wait=True)


async def main2():
    async with NbAioPool(max_concurrency=10, max_queue_size=1000) as pool:
        for i in range(100):
            await pool.submit(sample_task(i))  # 这样不阻塞当前for循环，是丢到queue队列后不管
           


async def main3():
    async with NbAioPool(max_concurrency=10, max_queue_size=1000) as pool:
        for i in range(100):
            # 演示一步到位得到结果，阻塞当前for循环
            await pool.run(sample_task(i))  # 和 await (await pool.submit(sample_task(i))) 等价。
            await (await pool.submit(sample_task(i)))  # 这样是直接得到异步函数的执行结果，阻塞当前for循环


async def main_batch_submit():
    async with NbAioPool(max_concurrency=10, max_queue_size=1000) as pool:
        coros = [sample_task(i) for i in range(100)]
        futures = await pool.batch_submit(coros)
        results = await asyncio.gather(*futures)
        print(results, len(results),len(futures))

async def main_batch_run():
    async with NbAioPool(max_concurrency=10, max_queue_size=1000) as pool:
        coros = [sample_task(i) for i in range(100)]
        results = await pool.batch_run(coros)
        print(results,len(results),len(coros))

if __name__ == "__main__":
    import nb_log

    # asyncio.run(main1())
    # asyncio.run(main2())
    # asyncio.run(main3())
    
    # asyncio.run(main_batch_submit())
    asyncio.run(main_batch_run())


    

