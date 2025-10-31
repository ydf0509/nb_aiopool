import asyncio
import time
import psutil
import os
import sys
from nb_libs import system_monitoring

from nb_aiopool.smart_aiopool import SmartAioPool 
from nb_aiopool.common_aiopool import CommonAioPool 
from nb_aiopool.no_queue_aiopool import NoQueueAioPool 
from nb_aiopool.no_queue_aiopool_use_condition import NoQueueAioPoolUseCondition 
async def small_task(x: int):
    """简单的任务，避免任务本身占用太多资源"""
    # await asyncio.sleep(100)  # 1ms
    if x%20000 == 0:
        print(f"{time.strftime('%H:%M:%S')},正在执行任务: {x}")
    return x * 2

pool = NoQueueAioPoolUseCondition(max_concurrency=1000)
async def test_100k_tasks():
    # pool = CommonAioPool(max_concurrency=1000, min_workers=10, auto_shutdown=True)
    # pool = CommonAioPool(max_concurrency=1000, )
    

    for i in range(1000001):
        # await pool.submit(small_task, i)
        await pool.submit(small_task(i))

if __name__ == "__main__":
    system_monitoring.thread_show_process_cpu_usage(1)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(test_100k_tasks())
    loop.run_forever()
