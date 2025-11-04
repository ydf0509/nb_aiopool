
"""
演示全局变量使用 nb_aiopool，可以多个函数和模块公用一个pool

注意：
要使代码最后一行一定要用 loop.run_forever() 来运行loop，不然就会导致程序提前退出，导致任务压根就没执行提前丢失。
"""

import asyncio
from nb_aiopool import NbAioPool


aiopool = NbAioPool(max_concurrency=3) # 演示全局变量使用 aiopool 的场景

async def fun_level1(x):
    await asyncio.sleep(1)
    print(x)
    await aiopool.submit(fun_level2(x*2,x*3))
    # await aiopool.submit(fun_level2,x*2,x*3)

async def fun_level2(a,b):
    await asyncio.sleep(2)
    print(a,b)

async def main():
    for i in range(30):
        await aiopool.submit(fun_level1(i)) 


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main()) 
    loop.run_forever()  # 切记不能少，不然就会导致程序提前退出，导致任务压根就没执行提前丢失。