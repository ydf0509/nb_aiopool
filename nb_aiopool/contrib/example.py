"""
nb_aio_task 使用示例

演示如何使用 aio_task 装饰器创建分布式异步任务队列
"""

import asyncio
from nb_aiopool.contrib import aio_task, batch_consume


# ==================== 定义任务 ====================

@aio_task(queue_name="my_queue1", max_concurrency=100)
async def my_fun1(x, y):
    """加法任务"""
    await asyncio.sleep(1)
    result = x + y
    print(f"my_fun1: {x} + {y} = {result}")
    return result


@aio_task(queue_name="my_queue2", max_concurrency=50)
async def my_fun2(a):
    """乘法任务"""
    await asyncio.sleep(1)
    result = a * 2
    print(f"my_fun2: {a} * 2 = {result}")
    return result


@aio_task(queue_name="my_queue3", max_concurrency=20)
async def complex_task(data: dict):
    """复杂对象任务（使用 pickle 序列化）"""
    await asyncio.sleep(0.5)
    name = data.get('name', 'Unknown')
    value = data.get('value', 0)
    print(f"complex_task: {name} -> {value}")
    return f"Processed {name}"


# ==================== 使用示例 ====================

async def example_1_basic():
    """示例1：基本用法 - 提交任务"""
    print("\n" + "="*60)
    print("示例1：基本用法 - 提交任务")
    print("="*60)
    
    # 提交任务到队列
    await my_fun1.submit(1, 2)
    await my_fun1.submit(10, 20)
    await my_fun2.submit(3)
    await my_fun2.submit(5)
    
    print(f"\n队列状态:")
    print(f"  my_queue1: {await my_fun1.get_queue_size()} 个任务")
    print(f"  my_queue2: {await my_fun2.get_queue_size()} 个任务")


async def example_2_consume():
    """示例2：启动消费者"""
    print("\n" + "="*60)
    print("示例2：启动消费者")
    print("="*60)
    
    # 方式1：分别启动每个任务的消费者
    # await my_fun1.consume()
    # await my_fun2.consume()
    
    # 方式2：批量启动多个消费者 ⭐ 推荐
    await batch_consume([my_fun1, my_fun2])


async def example_3_batch_submit():
    """示例3：批量提交任务"""
    print("\n" + "="*60)
    print("示例3：批量提交任务")
    print("="*60)
    
    # 批量提交 100 个任务
    for i in range(100):
        await my_fun1.submit(i, i+1)
    
    print(f"已提交 100 个任务到 my_queue1")
    print(f"队列大小: {await my_fun1.get_queue_size()}")


async def example_4_complex_data():
    """示例4：处理复杂对象"""
    print("\n" + "="*60)
    print("示例4：处理复杂对象")
    print("="*60)
    
    # 提交包含复杂对象的任务
    await complex_task.submit({'name': 'Task-A', 'value': 100})
    await complex_task.submit({'name': 'Task-B', 'value': 200})
    await complex_task.submit({'name': 'Task-C', 'value': 300})
    
    print(f"队列大小: {await complex_task.get_queue_size()}")
    
    # 启动消费者
    await complex_task.consume()


async def example_5_producer_consumer():
    """示例5：完整的生产者-消费者模式"""
    print("\n" + "="*60)
    print("示例5：生产者-消费者模式")
    print("="*60)
    
    async def producer():
        """生产者：持续提交任务"""
        print("📤 生产者启动")
        for i in range(50):
            await my_fun1.submit(i, i*2)
            await asyncio.sleep(0.1)  # 模拟实际业务间隔
        print("📤 生产者完成")
    
    async def consumer():
        """消费者：处理任务"""
        print("📥 消费者启动")
        await batch_consume([my_fun1, my_fun2])
    
    # 并发运行生产者和消费者
    await asyncio.gather(
        producer(),
        consumer(),
        return_exceptions=True
    )


async def example_6_clear_queue():
    """示例6：队列管理"""
    print("\n" + "="*60)
    print("示例6：队列管理")
    print("="*60)
    
    # 提交一些任务
    for i in range(10):
        await my_fun1.submit(i, i)
    
    print(f"提交前队列大小: {await my_fun1.get_queue_size()}")
    
    # 清空队列
    await my_fun1.clear_queue()
    
    print(f"清空后队列大小: {await my_fun1.get_queue_size()}")


# ==================== 主函数 ====================

async def main():
    """主函数：选择要运行的示例"""
    
    print("""
╔══════════════════════════════════════════════════════════╗
║  nb_aio_task - 简易分布式异步任务队列                    ║
║                                                          ║
║  基于 Redis + NbAioPool 实现                             ║
║  特点：简单、高效、支持并发控制和背压机制                 ║
╚══════════════════════════════════════════════════════════╝
    """)
    
    # 提示
    print("⚠️  请确保 Redis 服务已启动：redis-server\n")
    
    # 选择要运行的示例
    print("可用示例：")
    print("  1. 基本用法 - 提交任务")
    print("  2. 启动消费者")
    print("  3. 批量提交任务")
    print("  4. 处理复杂对象")
    print("  5. 生产者-消费者模式 ⭐")
    print("  6. 队列管理")
    
    choice = input("\n请选择示例 (1-6，默认5): ").strip() or "5"
    
    if choice == "1":
        await example_1_basic()
    elif choice == "2":
        await example_2_consume()
    elif choice == "3":
        await example_3_batch_submit()
    elif choice == "4":
        await example_4_complex_data()
    elif choice == "5":
        await example_5_producer_consumer()
    elif choice == "6":
        await example_6_clear_queue()
    else:
        print(f"无效选择: {choice}")
        return
    
    print("\n✅ 示例运行完成")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 程序已停止")
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()

