#!/usr/bin/env python3
# -*- coding: utf-8 -*-


"""
此代码证明 nb_aiopool 的必要性，证明异步并发池不是伪需求

演示无背压和有背压的的情况下，执行100万个非常简单的sleep任务，占用内存和cpu情况

通过ps_util包封装的 thread_show_process_cpu_usage(1) 和 thread_show_process_memory_usage(1) 每秒打印当前进程占用的cpu和内存情况。

如果采用 no_pool_main + aio_task_use_semaphore ，电脑长时间 100% cpu，演示到中途，内存占用迅速飙到10GB导致电脑死机。有些人还以为 async with semaphore 就万事大吉了呢。
如果采用 pool_main + aio_task ，电脑 cpu 使用率 1% ，内存持续稳定在 43M。

pool_main 里面用nb_aiopool 因为有背压，内存和cpu占用稳定性超一流，
no_pool_main 里面用 asyncio.Semaphore 没有背压，电脑直接挂掉死机，卡的你连鼠标键盘都无法使用，系统就崩溃死机了。
"""

import asyncio
from nb_aiopool import NbAioPool
from nb_libs.system_monitoring import thread_show_process_cpu_usage,thread_show_process_memory_usage



async def aio_task_use_semaphore(strx,n,semaphore):
    async with semaphore:
        await asyncio.sleep(5)
        print(n)
        return strx

async def aio_task(strx,n):
    await asyncio.sleep(5)
    print(n)
    return strx
   
async def no_pool_main(): 
    # 极端愚蠢的做法：直接创建1000万个任务
    print("正在创建1000万个任务...")

    semaphore = asyncio.Semaphore(1000)
    
    # 极端愚蠢，瞬间创建1000万个任务，导致内存激增，loop cpu压力也大
    tasks = [asyncio.create_task(aio_task_use_semaphore(f"{'task' * 100}_{i}",i,semaphore)) for i in range(1000000)] 
    # 执行所有请求
    print("开始执行aio_task任务...")
    await asyncio.gather(*tasks)
    print("执行aio_task任务完成")

async def pool_main():
    async with NbAioPool(max_concurrency=1000) as pool:
        for i in range(1000000): 
            await pool.submit(aio_task(f"{'task' * 100}_{i}",i)) # 只要你别保存100万futures到列表，内存就很小。
            # futures = [await pool.submit(aio_task(f"{'task' * 100}_{i}",i)) for i in range(1000000)] #  这样保存100万 futures 内存才大，nb_aiopool 不需要用户等待futures完成.




if __name__ == "__main__":
    thread_show_process_cpu_usage(1)
    thread_show_process_memory_usage(1)
    # asyncio.run(no_pool_main())
    asyncio.run(pool_main())