# nb_aiopool - asyncio 协程并发池

`nb_aiopool` 是一个轻量级、高性能的 `asyncio` 协程并发池，专为异步编程场景设计。

**核心价值：**
- ✅ **背压控制**：防止瞬间创建海量 Task，避免内存和 CPU 失控
- ✅ **简化代码**：无需在业务函数中侵入 `asyncio.Semaphore`
- ✅ **生产级稳定**：经过压测验证，100万并发任务（大字符串入参）内存稳定在 43MB

**为什么不用 `asyncio.Semaphore`？**  
`asyncio.Semaphore` 只能控制并发数量，但无法阻止你快速创建100万个 `asyncio.Task`！

当每个Task携带大字符串参数（如 `f"{'task' * 100}_{i}"`）和返回值时：
- ❌ `asyncio.Semaphore`：100万Task × 1.6KB = **10GB+内存** → 💥 电脑死机
- ✅ `NbAioPool`：背压保护，内存稳定在 **43MB** → ✨ 丝滑流畅

## 目录

- [1. 安装](#1-安装)
- [2. 快速开始](#2-快速开始)
- [3. NbAioPool 是伪需求吗？](#3-nbaiopool-是伪需求吗)
- [4. 核心概念：pool.submit vs pool.run](#4-核心概念poolsubmit-vs-poolrun)
- [5. 使用场景](#5-使用场景)
  - [5.1 局部变量用法（推荐）](#51-局部变量用法推荐)
  - [5.2 全局变量用法](#52-全局变量用法)
- [6. 稳定性对比：吊打 asyncio.Semaphore](#6-稳定性对比吊打-asynciosemaphore)
- [7. 与其他方案对比](#7-与其他方案对比)
- [8. 许可证](#8-许可证)

---

## 1. 安装

```bash
pip install nb_aiopool
```

**环境要求：** Python 3.7+

---

## 2. 快速开始

```python
import asyncio
from nb_aiopool import NbAioPool

async def my_task(x):
    """你的业务逻辑"""
    await asyncio.sleep(0.1)
    return x * 2

async def main():
    # 创建并发池：最大并发数 10，队列容量 1000
    async with NbAioPool(max_concurrency=10, max_queue_size=1000) as pool:
        # 方式1: 提交任务，返回 future（不阻塞）
        future = await pool.submit(my_task(5))
        result = await future  # 需要时再等待结果
        print(f"结果: {result}")
        
        # 方式2: 提交并立即等待结果（阻塞当前协程）
        result = await pool.run(my_task(10))
        print(f"结果: {result}")
        
        # 方式3: 批量提交
        futures = [await pool.submit(my_task(i)) for i in range(100)]
        results = await asyncio.gather(*futures)
        print(f"批量结果: {results}")

asyncio.run(main())
```

---

## 3. NbAioPool 是伪需求吗？

### 3.1🚨 问题：为什么 asyncio 也需要并发池？

很多人认为："协程这么轻量，为什么还需要并发池？直接用 `asyncio.Semaphore` 不就行了？"

**错！大错特错！**

### 3.2 ❌ 反面教材：只用 `asyncio.Semaphore`

```python
import asyncio

async def task_with_semaphore(big_data, task_id, semaphore):
    async with semaphore:  # 只控制并发数量
        await asyncio.sleep(0.1)
        # 返回大字符串，加剧内存占用
        return f"result_{'x' * 200}_{task_id}"

async def bad_example():
    semaphore = asyncio.Semaphore(1000)  # 限制1000并发
    
    # 🔥 灾难：瞬间创建1000万个 Task！
    # 每个Task携带大字符串参数，内存瞬间爆炸
    tasks = [
        asyncio.create_task(
            task_with_semaphore(f"{'task' * 100}_{i}", i, semaphore)
        ) 
        for i in range(10000000)
    ]
    
    # 此时你的电脑：
    # - 内存暴涨到 10GB+（每个Task都有大字符串！）
    # - CPU 100%
    # - 鼠标键盘卡死
    # - 系统崩溃重启
    
    await asyncio.gather(*tasks)
```

**问题分析：**

| 问题 | `asyncio.Semaphore` | `NbAioPool` |
|------|---------------------|-------------|
| 控制并发数量 | ✅ 支持 | ✅ 支持 |
| 背压机制 | ❌ 无法阻止快速创建Task | ✅ 队列满时自动阻塞 |
| 内存稳定性 | ❌ 100万Task占用10GB+ | ✅ 100万任务仅43MB |
| CPU占用 | ❌ 100%持续飙升 | ✅ 稳定在1% |
| 代码侵入性 | ❌ 需要改业务函数 | ✅ 无需改业务逻辑 |

### 3.3 ✅ 正确做法：使用 `NbAioPool`

```python
import asyncio
from nb_aiopool import NbAioPool

async def clean_task(big_data, task_id):
    """干净的业务逻辑，无需关心并发控制"""
    await asyncio.sleep(0.1)
    # 同样处理大字符串，但内存稳定
    return f"result_{'x' * 200}_{task_id}"

async def good_example():
    async with NbAioPool(max_concurrency=1000, max_queue_size=10000) as pool:
        # ✅ 背压机制：队列满时自动阻塞，不会瞬间创建100万Task
        # 即使每个任务携带大字符串，内存依然稳定
        for i in range(1000000):
            await pool.submit(clean_task(f"{'task' * 100}_{i}", i))
        
        # 电脑状态：
        # - 内存稳定在 43MB（有背压保护！）
        # - CPU 1%
        # - 一切丝滑流畅

asyncio.run(good_example())
```

### 3.4 nb_aiopool 吊打 分批处理并发协程 (预判了你的质疑)

肯定有人会质疑，没人那么愚蠢按照 `bad_example` 函数 中快速创建 1000万tasks，聪明人都会分批并发

- 有人会说只有笨瓜才会这样写代码，快速创建1000万个tasks
```python
async def bad_example():
    semaphore = asyncio.Semaphore(1000)  # 限制1000并发
    
    # 🔥 灾难：瞬间创建1000万个 Task！
    # 每个Task携带大字符串参数，内存瞬间爆炸
    tasks = [
        asyncio.create_task(
            task_with_semaphore(f"{'task' * 100}_{i}", i, semaphore)
        ) 
        for i in range(10000000)
    ]
    await asyncio.gather(*tasks)
```

- 你会说你会按下面分批
```python
async def safe_batch_processing():
    semaphore = asyncio.Semaphore(1000)  # 限制并发数量
    batch_size = 1000  # 每批处理1000个任务
    total_tasks = 10000000  # 总共1000万个任务
    
    for batch_start in range(0, total_tasks, batch_size):
        batch_end = min(batch_start + batch_size, total_tasks)
        print(f"处理批次: {batch_start} 到 {batch_end-1}")
        
        # 仅创建当前批次的任务
        batch_tasks = [
            asyncio.create_task(
                task_with_semaphore(f"{'task' * 100}_{i}", i, semaphore)
            )
            for i in range(batch_start, batch_end)
        ]
        
        # 等待当前批次完成
        batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

        # 可选：批次间短暂休眠，让系统资源回收
        await asyncio.sleep(0.01)

```

**分批的缺点：**

- **代码复杂度高**：需要手动管理批次循环、边界计算和批次间协调，代码冗长且容易出错。

- **动态负载不均衡**：每批固定数量的任务，无法根据系统实时负载动态调整，导致资源浪费或处理能力不足



**举例** 例如1000个任务作为一批次，如果999个任务0.1秒完成，但有1个任务卡了300秒，在绝大部分99%的时间里，服务的asyncio协程并发降低到1了，严重浪费 asyncio 并发高的好处。

**分批处理和nb_aiopool示意图**
分批处理：
[■■■■■■■■■■] → 等待300秒 → [■■■■■■■■■■] → ...
      ↑
    1个慢任务阻塞全部

NbAioPool：
[■□□□□□□□□□] → [■■■■■□□□□□] → 持续高效处理
  快任务完成后立即释放槽位

**小结：**相比之下，`NbAioPool` 提供了自动化的背压控制和持续的任务流处理，无需手动管理批次，代码更简洁且性能更稳定。


### 3.5 如果你说不分批执行，使用 生产者->asyncio.Queue->消费者 模式来实现 (再次预判了你的质疑)

那你说的刚好就是 `nb_aiopool` 了， `nb_aiopool` 就是 `生产者->asyncio.Queue->消费者` 实现的封装。 

`nb_aiopool` 就是减少了需要频繁临时手写 `定义queue + produce函数 + consume函数`

---

## 4. 核心概念：pool.submit vs pool.run

### 4.1 `pool.submit(coro)` - 提交任务，返回 Future

**特点：**
- ✅ 非阻塞：立即返回 `asyncio.Future` 对象
- ✅ 适合批量提交：可以快速提交大量任务
- ⚠️ 需要手动等待：稍后通过 `await future` 获取结果

**使用场景：** 需要并发执行多个任务，最后统一收集结果

```python
async def example_submit():
    async with NbAioPool(max_concurrency=10) as pool:
        # 批量提交100个任务
        futures = [await pool.submit(my_task(i)) for i in range(100)]
        
        # 可以先做其他事情
        print("任务已提交，现在可以做别的事")
        
        # 需要结果时再等待
        results = await asyncio.gather(*futures)
        print(f"结果: {results}")
```

### 4.2 `pool.run(coro)` - 提交任务并等待结果

**特点：**
- ✅ 一步到位：直接返回任务执行结果
- ✅ 代码简洁：相当于 `await (await pool.submit(coro))`
- ⚠️ 阻塞当前协程：会等待任务完成

**使用场景：** 需要立即使用任务结果

```python
async def example_run():
    async with NbAioPool(max_concurrency=10) as pool:
        # 逐个执行并获取结果
        for i in range(100):
            result = await pool.run(my_task(i))
            print(f"第 {i} 个任务结果: {result}")
```

### 4.3 对比总结

```python
# submit: 快速提交，稍后等待
future = await pool.submit(my_task(5))
# ... 可以做其他事情 ...
result = await future  # 需要时再等待

# run: 提交并立即等待（等价于上面两行）
result = await pool.run(my_task(5))
```

**选择建议：**
- 批量并发任务 → 用 `submit` + `asyncio.gather`
- 顺序执行任务 → 用 `run`

---

## 5. 使用场景

### 5.1 局部变量用法（推荐）

适用于 `asyncio.run()` 启动的应用。

#### 5.1.1 使用 `async with`（最佳实践）

```python
import asyncio
from nb_aiopool import NbAioPool

async def sample_task(x: int):
    await asyncio.sleep(0.1)
    print(x)
    return x * 2

async def main():
    # 推荐：使用 async with，自动处理资源释放
    async with NbAioPool(max_concurrency=10, max_queue_size=1000) as pool:
        # 方式1: submit 批量提交
        futures = [await pool.submit(sample_task(i)) for i in range(100)]
        results = await asyncio.gather(*futures)
        print("结果:", results)
        
        # 方式2: run 逐个执行
        for i in range(10):
            result = await pool.run(sample_task(i))
            print(f"任务 {i} 结果: {result}")
    
    # async with 退出时自动调用 pool.shutdown(wait=True)

asyncio.run(main())
```

#### 5.1.2 手动管理生命周期

```python
async def main():
    pool = NbAioPool(max_concurrency=10, max_queue_size=1000)
    
    # 提交任务
    futures = [await pool.submit(sample_task(i)) for i in range(100)]
    results = await asyncio.gather(*futures)
    print("结果:", results)
    
    # ⚠️ 如果你不写await asyncio.gather(*futures)，必须手动调用 shutdown，否则任务会丢失！
    await pool.shutdown(wait=True)

asyncio.run(main())
```

### 5.2 全局变量用法

适用于需要跨模块、跨函数共享 pool 的场景，或使用 `loop.run_forever()` 的应用。

**完整示例：** 参考 `tests/t_global_nb_aiopool.py`

```python
import asyncio
from nb_aiopool import NbAioPool

# 全局 pool，可在多个模块、函数中共享
aiopool = NbAioPool(max_concurrency=3, max_queue_size=1000)

async def fun_level1(x):
    """第一层业务逻辑"""
    await asyncio.sleep(1)
    print(f"Level1: {x}")
    # 在任务内部可以继续提交子任务
    await aiopool.submit(fun_level2(x*2, x*3))

async def fun_level2(a, b):
    """第二层业务逻辑"""
    await asyncio.sleep(2)
    print(f"Level2: {a}, {b}")

async def main():
    # 批量提交任务
    for i in range(30):
        await aiopool.submit(fun_level1(i))

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
    
    # ⚠️ 关键：使用 run_forever() 时必须加这行
    # 否则任务会因为程序提前退出而丢失
    loop.run_forever()
```

**注意事项：**

1. **全局 pool 初始化：** 在模块顶层创建，确保所有函数可访问
2. **程序需要长期运行：** 使用 `loop.run_forever()` 时，任务会持续执行

---

## 6. 稳定性对比：吊打 asyncio.Semaphore

### 6.1 压测场景

**任务：** 执行 100 万个简单的 `asyncio.sleep(5)` 任务，并发数 1000

**完整代码：** 参考 `tests/t_press_web/nopool_test_sleep.py`

### 6.2 方案1：只用 `asyncio.Semaphore`（灾难版）

```python
async def aio_task_use_semaphore(big_input_data, n, semaphore):
    async with semaphore:
        await asyncio.sleep(5)
        print(n)
        # 返回大字符串，进一步加剧内存占用
        return f"result_{'x' * 200}_{n}_{big_input_data[:50]}"

async def no_pool_main():
    print("正在创建100万个任务...")
    semaphore = asyncio.Semaphore(1000)
    
    # 🔥 灾难：瞬间创建100万个Task
    # 每个Task都有大字符串入参和返回值，内存爆炸式增长！
    tasks = [
        asyncio.create_task(
            aio_task_use_semaphore(f"{'task' * 100}_{i}", i, semaphore)
        ) 
        for i in range(1000000)
    ]
    
    print("开始执行任务...")
    await asyncio.gather(*tasks)
    print("执行完成")

asyncio.run(no_pool_main())
```

**资源占用（实测）：**

| 时间 | 内存 | CPU | 状态 |
|------|------|-----|------|
| 0s | 50MB | 100% | 创建Task中 |
| 10s | 3GB | 100% | 内存持续上涨 |
| 30s | 10GB+ | 100% | 系统卡死 |
| 45s | 💥 | 💥 | **电脑死机重启** |

### 6.3 方案2：使用 `NbAioPool`（稳如老狗版）

```python
async def aio_task(big_input_data, n):
    """干净的业务逻辑，无需 semaphore"""
    await asyncio.sleep(5)
    print(n)
    # 同样返回大字符串，但有背压保护，内存依然稳定
    return f"result_{'x' * 200}_{n}_{big_input_data[:50]}"

async def pool_main():
    async with NbAioPool(max_concurrency=1000, max_queue_size=10000) as pool:
        for i in range(1000000):
            # ✅ 有背压：队列满时自动阻塞，不会瞬间创建100万Task
            # 即使每个任务都有大字符串入参和返回值，内存依然稳定！
            await pool.submit(aio_task(f"{'task' * 100}_{i}", i))

asyncio.run(pool_main())
```

**资源占用（实测）：**

| 时间 | 内存 | CPU | 状态 |
|------|------|-----|------|
| 0s | 43MB | 1% | 稳定运行 |
| 60s | 43MB | 1% | 稳定运行 |
| 300s | 43MB | 1% | 稳定运行 |
| 1小时+ | 43MB | 1% | **持续稳定** ✅ |

### 6.4 对比总结

```
┌─────────────────────────────────────────────────────────┐
│         asyncio.Semaphore          vs    NbAioPool      │
├─────────────────────────────────────────────────────────┤
│ 内存占用：    10GB+                vs       43MB        │
│ CPU占用：     100%持续             vs       1%          │
│ 稳定性：      30秒内死机           vs       持续稳定    │
│ 背压机制：    ❌ 无                vs       ✅ 有       │
│ 代码侵入：    ❌ 需改业务函数      vs       ✅ 无侵入  │
└─────────────────────────────────────────────────────────┘
```

**结论：**

> **为什么内存差距这么大？**  
> 因为 `asyncio.Semaphore` 瞬间创建100万个Task对象，每个Task都保存着：
> - 大字符串入参：`f"{'task' * 100}_{i}"` ≈ 400 字节
> - 大字符串返回值：`f"result_{'x' * 200}_{task_id}"` ≈ 200 字节  
> - Task对象本身的开销：≈ 1KB
> 
> **100万个Task × 1.6KB ≈ 1.6GB**，再加上Python对象管理开销，轻松超过10GB！
>
> 而 `NbAioPool` 有背压机制，同时只保持 `max_concurrency + max_queue_size` 个任务在内存中，
> 即使100万任务，内存也稳定在 43MB！
>
> **试想一下：** 如果你的异步函数入参和返回值是更大的对象（如几KB的字典、图片数据），  
> 并且需要创建 1000 万个 tasks，不使用 `NbAioPool`，  
> 你需要购买阿里云 **10TB 内存** 的服务器才能顶得住！




---

## 7. 与其他方案对比

### 7.1 vs `asyncio.Semaphore`

| 特性 | `asyncio.Semaphore` | `NbAioPool` |
|------|---------------------|-------------|
| 并发控制 | ✅ | ✅ |
| 背压机制 | ❌ | ✅ |
| 内存稳定 | ❌ | ✅ |
| 代码侵入 | ❌ 需改业务函数 | ✅ 无侵入 |
| 使用复杂度 | 中 | 低 |

### 7.2 vs `asyncio.TaskGroup` (Python 3.11+)

| 特性 | `asyncio.TaskGroup` | `NbAioPool` |
|------|---------------------|-------------|
| Python 版本要求 | 3.11+ | 3.7+ |
| 并发数控制 | ❌ | ✅ |
| 背压机制 | ❌ | ✅ |
| 全局共享 | ❌ 不适合 | ✅ 支持 |
| 异常处理 | ✅ 优秀 | ✅ |

**使用建议：**
- `TaskGroup`：适合局部任务组的异常管理
- `NbAioPool`：适合需要并发控制和背压的场景

### 7.3 vs `async_pool_executor`

**完全不同的使用场景！**

| 库 | 环境 | 用途 |
|----|----|------|
| `async_pool_executor` | **同步环境** | 在同步代码中调用异步函数 |
| `NbAioPool` | **异步环境** | 在异步代码中管理并发 |

**举例说明：**

```python
# async_pool_executor: 同步代码调用异步函数
from async_pool_executor import AsyncPoolExecutor

executor = AsyncPoolExecutor()
# 在同步函数中调用异步函数
executor.submit(async_func, arg1, arg2)
# NbAioPool: 异步代码管理并发
from nb_aiopool import NbAioPool

async def main():
    async with NbAioPool(max_concurrency=100) as pool:
        # 在异步环境中控制并发
        await pool.submit(async_func(arg1, arg2))
```

---

## 8. API 参考

### 8.1 `NbAioPool`

```python
class NbAioPool:
    def __init__(self, max_concurrency: int = 100, max_queue_size: int = 1000):
        """
        创建并发池
        
        参数:
            max_concurrency: 最大并发任务数（同时运行的worker数量）
            max_queue_size: 任务队列最大容量（背压控制）
        """
```

### 8.2 主要方法

```python
async def submit(self, coro: Coroutine, block: bool = True) -> asyncio.Future:
    """
    提交任务，返回 Future 对象
    
    参数:
        coro: 协程对象（注意：是协程对象，不是函数！）
        block: 队列满时是否阻塞等待（True: 等待，False: 立即抛异常）
    
    返回:
        asyncio.Future 对象
    
    示例:
        future = await pool.submit(my_task(10))
        result = await future
    """

async def run(self, coro: Coroutine, block: bool = True) -> Any:
    """
    提交任务并等待结果（等价于 await pool.submit(coro)）
    
    参数:
        coro: 协程对象
        block: 队列满时是否阻塞等待
    
    返回:
        任务执行结果
    
    示例:
        result = await pool.run(my_task(10))
    """

async def shutdown(self, wait: bool = True):
    """
    关闭池
    
    参数:
        wait: 是否等待所有任务完成
    """
```

### 8.3 上下文管理器

```python
async with NbAioPool(max_concurrency=10) as pool:
    await pool.submit(my_task(1))
    # 退出时自动调用 shutdown(wait=True)
```

---

## 9. 最佳实践

### ✅ 推荐做法

```python
# 1. 使用 async with 管理生命周期
async with NbAioPool(max_concurrency=100) as pool:
    await pool.submit(task())

# 2. 根据场景选择并发数
# - CPU密集型（少）: max_concurrency = CPU核心数 * 2
# - IO密集型（多）: max_concurrency = 100 ~ 1000
# - 网络爬虫（超多）: max_concurrency = 1000 ~ 10000

# 3. 队列大小设置
# max_queue_size 应该 >= max_concurrency * 10

# 4. 批量任务用 submit + gather
futures = [await pool.submit(task(i)) for i in range(1000)]
results = await asyncio.gather(*futures)
```

---

## 10. 常见问题



### Q2: `async with` 和手动 `shutdown` 有什么区别？

```python
# 方式1: async with（推荐）
async with NbAioPool(max_concurrency=10) as pool:
    await pool.submit(task())
# 自动调用 shutdown(wait=True)

# 方式2: 手动管理
pool = NbAioPool(max_concurrency=10)
await pool.submit(task())
await pool.shutdown(wait=True)  # 必须手动调用！
```

**建议：** 优先使用 `async with`，避免忘记 `shutdown` 导致任务丢失.



---

## 10. 许可证

MIT License

---


## 11 nb_aiopool 和 async-pool-executor 区别

nb_aiopool 的定位与 async-pool-executor (例如 这个库 或 funboost 内置的实现) 完全不同，它们解决了不同场景下的问题，不存在竞争关系。

`nb_aiopool`  
和以前的这两个已开发的 `async_pool_executor` 作用不同。

https://github.com/ydf0509/async_pool_executor 
https://github.com/ydf0509/funboost/blob/master/funboost/concurrent_pool/async_pool_executor.py

`async_pool_executor` 是在同步环境中去 pool.submit 任务给一个loop并发运行多个coro ，   
当一个框架需要兼容调度同步和异步并发时候用这，  
例如`funboost`总体生态语法是同步的，需要依靠使用`async_pool_executor` 实现 `asyncio` 模式并发。 

`nb_aiopool` 是 在异步环境中去 await pool.submit ，纯脆为了异步生态而生。  


简单来说：
*   **`async_pool_executor`：是**一座桥梁**，连接了**同步世界**和**异步世界**。**
    *   它的工作是在一个**同步的**代码环境中，能够方便地调用并执行**异步的**函数（协程），而不用把整个应用都变成 `async/await`。
*   **`nb_aiopool`：是一个**交通管制系统**，它**完全生活在异步世界内部**。**
    *   它的工作是在一个**已经存在的**异步代码环境中，去管理和限制并发任务的流量，防止交通堵塞（资源耗尽）。

---

## 12. 相关链接

- **GitHub:** https://github.com/ydf0509/nb_aiopool
- **PyPI:** https://pypi.org/project/nb-aiopool/
- **作者:** ydf0509





