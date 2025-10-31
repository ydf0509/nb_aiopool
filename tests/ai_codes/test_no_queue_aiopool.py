"""测试 NoQueueAioPool 的逻辑正确性"""
import asyncio
import sys
import os
import time

# 添加父目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from nb_aiopool.no_queue_aiopool import NoQueueAioPool


async def sample_task(x: int, duration: float = 0.1):
    """示例异步任务"""
    await asyncio.sleep(duration)
    print(f"Task {x} completed")
    return x * 2


async def test_basic_submit():
    """测试1: 基本的 submit 功能"""
    print("=" * 50)
    print("测试1: 基本 submit 功能")
    print("=" * 50)
    
    pool = NoQueueAioPool(max_concurrency=3)
    
    future1 = await pool.submit(sample_task(1, 0.05))
    future2 = await pool.submit(sample_task(2, 0.05))
    future3 = await pool.submit(sample_task(3, 0.05))
    
    results = await asyncio.gather(future1, future2, future3)
    print(f"✅ 结果: {results}")
    assert results == [2, 4, 6]
    print("✅ 测试1通过!\n")


async def test_max_concurrency():
    """测试2: 验证最大并发数限制"""
    print("=" * 50)
    print("测试2: 验证最大并发数限制")
    print("=" * 50)
    
    pool = NoQueueAioPool(max_concurrency=3)
    
    # 记录同时运行的任务数
    running_count = []
    lock = asyncio.Lock()
    
    async def tracked_task(x: int):
        async with lock:
            running_count.append(len(pool.tasks))
            current = len(pool.tasks)
        print(f"  Task {x} 开始，当前运行数: {current}")
        await asyncio.sleep(0.1)
        return x * 2
    
    # 提交5个任务，但最多只能同时运行3个
    futures = []
    for i in range(5):
        future = await pool.submit(tracked_task(i))
        futures.append(future)
    
    results = await asyncio.gather(*futures)
    
    # 验证从未超过最大并发数
    max_running = max(running_count)
    print(f"✅ 最大并发数记录: {running_count}")
    print(f"✅ 实际最大并发: {max_running}")
    assert max_running <= 3, f"超过最大并发数: {max_running} > 3"
    print("✅ 测试2通过!\n")


async def test_run_method():
    """测试3: 测试 run 方法"""
    print("=" * 50)
    print("测试3: run 方法")
    print("=" * 50)
    
    pool = NoQueueAioPool(max_concurrency=5)
    
    # run 应该直接返回结果，不是 Future
    result1 = await pool.run(sample_task(10, 0.05))
    result2 = await pool.run(sample_task(20, 0.05))
    result3 = await pool.run(sample_task(30, 0.05))
    
    print(f"✅ 结果: {result1}, {result2}, {result3}")
    assert result1 == 20
    assert result2 == 40
    assert result3 == 60
    print("✅ 测试3通过!\n")


async def test_error_handling():
    """测试4: 错误处理"""
    print("=" * 50)
    print("测试4: 错误处理")
    print("=" * 50)
    
    async def failing_task(x: int):
        await asyncio.sleep(0.01)
        if x == 2:
            raise ValueError(f"Task {x} failed!")
        return x * 2
    
    pool = NoQueueAioPool(max_concurrency=5)
    
    future1 = await pool.submit(failing_task(1))
    future2 = await pool.submit(failing_task(2))  # 会失败
    future3 = await pool.submit(failing_task(3))
    
    result1 = await future1
    print(f"✅ Task 1 结果: {result1}")
    
    try:
        await future2
        print("❌ 应该抛出异常!")
        assert False
    except ValueError as e:
        print(f"✅ Task 2 正确抛出异常: {e}")
    
    result3 = await future3
    print(f"✅ Task 3 结果: {result3}")
    
    print("✅ 测试4通过!\n")


async def test_wait_method():
    """测试5: wait 方法"""
    print("=" * 50)
    print("测试5: wait 方法")
    print("=" * 50)
    
    pool = NoQueueAioPool(max_concurrency=5)
    
    # 提交任务但不等待
    for i in range(10):
        await pool.submit(sample_task(i, 0.05))
    
    print(f"  提交了10个任务，当前运行: {len(pool.tasks)}")
    
    # 使用 wait 等待所有任务完成
    await pool.wait()
    
    print(f"  等待完成后，剩余任务: {len(pool.tasks)}")
    assert len(pool.tasks) == 0
    print("✅ 测试5通过!\n")


async def test_race_condition():
    """测试6: 并发提交时的竞态条件"""
    print("=" * 50)
    print("测试6: 并发提交竞态条件测试（关键测试）")
    print("=" * 50)
    
    pool = NoQueueAioPool(max_concurrency=5)
    max_observed = []
    
    async def tracking_task(x: int):
        # 记录提交时的任务数
        max_observed.append(len(pool.tasks))
        await asyncio.sleep(0.05)
        return x
    
    # 并发提交大量任务
    tasks = []
    for i in range(20):
        task = asyncio.create_task(pool.submit(tracking_task(i)))
        tasks.append(task)
    
    # 等待所有提交完成
    futures = await asyncio.gather(*tasks)
    
    # 等待所有任务执行完成
    results = await asyncio.gather(*futures)
    
    # 检查是否有任何时刻超过最大并发数
    max_concurrent = max(max_observed)
    print(f"  观察到的最大并发数: {max_concurrent}")
    print(f"  并发数分布: {sorted(max_observed)}")
    
    if max_concurrent > 5:
        print(f"❌ 发现竞态条件！最大并发数 {max_concurrent} 超过限制 5")
        assert False, f"竞态条件：{max_concurrent} > 5"
    else:
        print(f"✅ 未发现竞态条件，最大并发数控制正确")
    
    print("✅ 测试6通过!\n")


async def test_stress():
    """测试7: 压力测试"""
    print("=" * 50)
    print("测试7: 压力测试 (100个任务)")
    print("=" * 50)
    
    pool = NoQueueAioPool(max_concurrency=10)
    
    start = time.time()
    
    async def quick_task(x: int):
        await asyncio.sleep(0.01)
        return x * 2
    
    # 提交100个任务
    futures = []
    for i in range(100):
        future = await pool.submit(quick_task(i))
        futures.append(future)
    
    results = await asyncio.gather(*futures)
    
    elapsed = time.time() - start
    
    print(f"  完成 {len(results)} 个任务")
    print(f"  用时: {elapsed:.2f} 秒")
    print(f"  结果正确: {results == [i * 2 for i in range(100)]}")
    
    assert results == [i * 2 for i in range(100)]
    print("✅ 测试7通过!\n")


async def main():
    """运行所有测试"""
    print("\n🚀 开始测试 NoQueueAioPool\n")
    
    await test_basic_submit()
    await test_max_concurrency()
    await test_run_method()
    await test_error_handling()
    await test_wait_method()
    await test_race_condition()  # 关键测试
    await test_stress()
    
    print("=" * 50)
    print("🎉 所有测试通过！逻辑正确！")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())

