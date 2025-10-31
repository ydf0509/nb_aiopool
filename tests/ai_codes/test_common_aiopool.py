"""测试 CommonAioPool 的协程对象 API"""
import asyncio
import sys
import os

# 添加父目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from nb_aiopool.common_aiopool import CommonAioPool


async def sample_task(x: int):
    """示例异步任务"""
    await asyncio.sleep(0.05)
    print(f"Task {x} = {x * 2}")
    return x * 2


async def test_submit():
    """测试 submit 方法"""
    print("=" * 50)
    print("测试1: submit 接收协程对象")
    print("=" * 50)
    
    pool = CommonAioPool(max_concurrency=5, max_queue_size=100)
    
    # 提交协程对象
    future1 = await pool.submit(sample_task(1))
    future2 = await pool.submit(sample_task(2))
    future3 = await pool.submit(sample_task(3))
    
    # 等待结果
    results = await asyncio.gather(future1, future2, future3)
    print(f"✅ 结果: {results}")
    assert results == [2, 4, 6]
    
    await pool.shutdown(wait=True)
    print("✅ 测试1通过!\n")


async def test_run():
    """测试 run 方法"""
    print("=" * 50)
    print("测试2: run 接收协程对象")
    print("=" * 50)
    
    pool = CommonAioPool(max_concurrency=5, max_queue_size=100)
    
    # 使用 run 直接获取结果
    result1 = await pool.run(sample_task(10))
    result2 = await pool.run(sample_task(20))
    result3 = await pool.run(sample_task(30))
    
    print(f"✅ 结果: {result1}, {result2}, {result3}")
    assert result1 == 20
    assert result2 == 40
    assert result3 == 60
    
    await pool.shutdown(wait=True)
    print("✅ 测试2通过!\n")


async def test_context_manager():
    """测试上下文管理器"""
    print("=" * 50)
    print("测试3: 上下文管理器")
    print("=" * 50)
    
    async with CommonAioPool(max_concurrency=5, max_queue_size=100) as pool:
        futures = [await pool.submit(sample_task(i)) for i in range(10)]
        results = await asyncio.gather(*futures)
        print(f"✅ 完成 {len(results)} 个任务")
        assert results == [i * 2 for i in range(10)]
    
    print("✅ 测试3通过!\n")


async def test_batch_submit():
    """测试批量提交"""
    print("=" * 50)
    print("测试4: 批量提交协程对象")
    print("=" * 50)
    
    pool = CommonAioPool(max_concurrency=10, max_queue_size=200)
    
    # 批量提交
    futures = [await pool.submit(sample_task(i)) for i in range(20)]
    results = await asyncio.gather(*futures)
    
    print(f"✅ 共完成 {len(results)} 个任务")
    assert results == [i * 2 for i in range(20)]
    
    await pool.shutdown(wait=True)
    print("✅ 测试4通过!\n")


async def test_error_handling():
    """测试错误处理"""
    print("=" * 50)
    print("测试5: 错误处理")
    print("=" * 50)
    
    async def failing_task(x: int):
        await asyncio.sleep(0.01)
        if x == 2:
            raise ValueError(f"Task {x} failed!")
        return x * 2
    
    pool = CommonAioPool(max_concurrency=5, max_queue_size=100)
    
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
    
    await pool.shutdown(wait=True)
    print("✅ 测试5通过!\n")


async def test_queue_full():
    """测试队列满的情况"""
    print("=" * 50)
    print("测试6: 队列满处理（非阻塞）")
    print("=" * 50)
    
    async def slow_task(x: int):
        await asyncio.sleep(0.5)
        return x * 2
    
    pool = CommonAioPool(max_concurrency=2, max_queue_size=5)
    
    # 快速提交大量任务，直到队列满
    futures = []
    for i in range(5):
        future = await pool.submit(slow_task(i))
        futures.append(future)
    
    # 再提交一个，队列应该满了（非阻塞模式）
    try:
        future = await pool.submit(slow_task(999), block=False)
        result = await future
        print(f"❌ 应该抛出 Queue full 异常，但得到结果: {result}")
    except RuntimeError as e:
        print(f"✅ 正确处理队列满: {e}")
    
    # 等待之前的任务完成
    results = await asyncio.gather(*futures)
    print(f"✅ 完成 {len(results)} 个任务")
    
    await pool.shutdown(wait=True)
    print("✅ 测试6通过!\n")


async def main():
    """运行所有测试"""
    print("\n🚀 开始测试 CommonAioPool 协程对象 API\n")
    
    await test_submit()
    await test_run()
    await test_context_manager()
    await test_batch_submit()
    await test_error_handling()
    await test_queue_full()
    
    print("=" * 50)
    print("🎉 所有测试通过!")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())

