"""
测试 NoQueueAioPool 的死锁检测和优化功能
"""
import asyncio
import warnings
from nb_aiopool import NoQueueAioPool

async def nested_task(x):
    """嵌套的子任务"""
    await asyncio.sleep(0.1)
    print(f"  nested_task {x} finished")
    return x * 2

async def parent_task(pool, x):
    """父任务，会在内部提交子任务"""
    await asyncio.sleep(0.1)
    print(f"parent_task {x} started")
    # 这里会触发死锁检测警告
    result = await pool.submit(nested_task(x))
    print(f"parent_task {x} got result: {await result}")
    return x

# ==========================================
# 测试1: 演示死锁问题（启用警告）
# ==========================================
async def test_deadlock_with_warning():
    print("\n" + "="*60)
    print("测试1: 演示死锁风险（启用警告检测）")
    print("="*60)
    
    # 创建一个小容量的pool，容易触发死锁
    pool = NoQueueAioPool(max_concurrency=3, enable_nested_task_warning=True)
    
    print(f"Pool 状态: {pool}")
    
    # 捕获警告
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        
        try:
            # 提交任务，会触发死锁
            tasks = [await pool.submit(parent_task(pool, i)) for i in range(5)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            print(f"结果: {results}")
        except Exception as e:
            print(f"捕获异常: {e}")
        
        # 显示警告信息
        if w:
            print(f"\n捕获到 {len(w)} 个警告:")
            for warning in w:
                print(f"  ⚠️  {warning.message}")

# ==========================================
# 测试2: 使用 timeout 避免永久阻塞
# ==========================================
async def test_with_timeout():
    print("\n" + "="*60)
    print("测试2: 使用 timeout 避免死锁")
    print("="*60)
    
    pool = NoQueueAioPool(max_concurrency=3, enable_nested_task_warning=False)
    
    async def parent_with_timeout(pool, x):
        await asyncio.sleep(0.1)
        print(f"parent {x} started")
        try:
            # 使用 timeout，如果1秒内无法提交则超时
            result = await pool.submit(nested_task(x), timeout=1.0)
            return await result
        except TimeoutError as e:
            print(f"  ⚠️  parent {x} timeout: {e}")
            return None
    
    tasks = [await pool.submit(parent_with_timeout(pool, i)) for i in range(5)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    print(f"结果: {results}")

# ==========================================
# 测试3: 使用 block=False 非阻塞模式
# ==========================================
async def test_non_blocking():
    print("\n" + "="*60)
    print("测试3: 使用非阻塞模式 (block=False)")
    print("="*60)
    
    pool = NoQueueAioPool(max_concurrency=3, enable_nested_task_warning=False)
    
    async def parent_non_blocking(pool, x):
        await asyncio.sleep(0.1)
        print(f"parent {x} started")
        try:
            # 非阻塞提交，如果池满则立即失败
            result = await pool.submit(nested_task(x), block=False)
            return await result
        except RuntimeError as e:
            print(f"  ⚠️  parent {x} 提交失败: 池已满")
            # 降级方案：直接执行，不通过池
            return await nested_task(x)
    
    tasks = [await pool.submit(parent_non_blocking(pool, i)) for i in range(5)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    print(f"结果: {results}")

# ==========================================
# 测试4: 正确的做法 - 增大并发数
# ==========================================
async def test_correct_way():
    print("\n" + "="*60)
    print("测试4: 正确做法 - 增大 max_concurrency")
    print("="*60)
    
    # 为嵌套任务预留足够空间
    pool = NoQueueAioPool(max_concurrency=100, enable_nested_task_warning=False)
    
    async def parent_correct(pool, x):
        await asyncio.sleep(0.1)
        print(f"parent {x} started")
        result = await pool.submit(nested_task(x))
        final = await result
        print(f"parent {x} finished with result: {final}")
        return final
    
    tasks = [await pool.submit(parent_correct(pool, i)) for i in range(10)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    print(f"结果: {results}")
    print(f"Pool 状态: {pool}")

# ==========================================
# 测试5: 使用独立的 pool
# ==========================================
async def test_separate_pools():
    print("\n" + "="*60)
    print("测试5: 使用独立的 pool 处理嵌套任务")
    print("="*60)
    
    pool_level1 = NoQueueAioPool(max_concurrency=3, enable_nested_task_warning=False)
    pool_level2 = NoQueueAioPool(max_concurrency=10, enable_nested_task_warning=False)
    
    async def parent_separate_pool(x):
        await asyncio.sleep(0.1)
        print(f"parent {x} started (pool1: {pool_level1.active_count} tasks)")
        # 使用不同的 pool
        result = await pool_level2.submit(nested_task(x))
        final = await result
        print(f"parent {x} finished with result: {final}")
        return final
    
    tasks = [await pool_level1.submit(parent_separate_pool(i)) for i in range(5)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    print(f"结果: {results}")
    print(f"Pool1 状态: {pool_level1}")
    print(f"Pool2 状态: {pool_level2}")


async def main():
    """运行所有测试"""
    await test_deadlock_with_warning()
    await test_with_timeout()
    await test_non_blocking()
    await test_correct_way()
    await test_separate_pools()
    
    print("\n" + "="*60)
    print("✅ 所有测试完成")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())

