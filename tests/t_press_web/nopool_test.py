#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HTTP压力测试工具 - 无池版本（极端愚蠢版）

用于向指定主机和端口发送大量HTTP请求以进行性能测试。
此版本不使用任何连接池或任务池，而是直接创建1000万个任务，极端浪费资源。
说明，即使是在asyncio 编程生态，并发池任然是有必要的。

此版本用于演示aiopool的价值：
1. 控制并发数量，避免系统过载
2. 复用任务（task）资源，提高效率
3. 合理管理内存使用
4. 控制task的创建速度，避免瞬间创建大量任务导致内存激增
"""

import asyncio
import aiohttp


async def make_request(url, session, semaphore):
    """发送单个HTTP请求"""
    async with semaphore:
        try:
            async with session.get(url) as response:
                await response.read()
        except:
            pass


async def main():
    """主函数 - 请求1000万次"""
    url = "http://localhost:8000"
    
    # 极端愚蠢的做法：直接创建1000万个任务
    print("正在创建1000万个任务...")

    semaphore = asyncio.Semaphore(1000)
    # 创建共享的session和semaphore
    async with aiohttp.ClientSession() as session:
        # 极端愚蠢，瞬间创建1000万个任务，导致内存激增，loop cpu压力也大
        tasks = [asyncio.create_task(make_request(url, session, semaphore)) for _ in range(10000000)] 
        # 执行所有请求
        print("开始执行请求...")
        await asyncio.gather(*tasks)
        print("执行完成")


if __name__ == "__main__":
    asyncio.run(main())