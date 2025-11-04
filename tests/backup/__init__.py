from nb_aiopool.smart_aiopool import SmartAioPool , shutdown_all_smart_aiopools,smart_run
from nb_aiopool.common_aiopool import CommonAioPool ,shutdown_all_common_aiopools
from nb_aiopool.no_queue_aiopool import NoQueueAioPool ,wait_all_no_queue_aiopools
from nb_aiopool.no_queue_aiopool_use_condition import NoQueueAioPoolUseCondition ,wait_all_no_queue_aiopools_use_condition


async def wait_all_types_aiopools():
    """
    万能的等待所有类型的aiopool的任务完成，万能的等待所有任务完成的方法，不需要管用的是什么类型的 aiopool
    放在程序退出前执行，在你的async def 的入口函数的最后一行写 await wait_all_types_aiopools()
    """
    await shutdown_all_smart_aiopools() # 这个可以不需要，因为 SmartAioPool 有黑科技来复杂实现。
    await shutdown_all_common_aiopools()
    await wait_all_no_queue_aiopools()
    await wait_all_no_queue_aiopools_use_condition()