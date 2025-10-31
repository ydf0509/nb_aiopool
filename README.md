# 1 nb_aiopool - 异步IO并发池

nb_aiopool 是 asyncio 协程池,提供多种方式实现 协程并发池。

包括：
- SmartAioPool：高级智能并发池
- CommonAioPool：普通并发池
- NoQueueAioPool：无队列并发池

## 1.1 asyncio 为什么也需要协程并发池？

通常情况下 asyncio 生态不需要使用并发池，创建一个协程比线程成本低太多，所以aio并发池不流行，也没内置去实现，没有同步编程中线程池那么刚需。

但是asyncio生态如果要设置并发数量，需要入侵去源函数加 `asyncio.Semaphore(1000)` 来控制并发数量，这不好。

而且 例子1.6的 1000并发压测web 1000万次举例，你如果不用 asyncio 并发池，
那你直接写 `tasks = [asyncio.create_task(make_request(url, session, semaphore)) for _ in range(10000000)]` 那就太蠢了。

`make_request`虽然有 `asyncio.Semaphore(1000)` ,但是也迅速编排1000万个task，造成内存 cpu loop压力都很大，  
而如果使用nb_aiopool 可以有序控制程序的task创建速度。

## 1.2 安装

```bash
pip install nb_aiopool
```

## 1.3  快速开始

```python
from nb_aiopool import SmartAioPool

async def my_task(x):
    await asyncio.sleep(1)
    return x * 2

async def main():
    # 创建一个并发池，最大并发数为10
    pool = SmartAioPool(max_concurrency=10)
    
    future = await pool.submit(my_task,1) # 提交任务，返回future对象，不阻塞当前协程
    # result = await future # 等待任务完成，获取结果
    result = await pool.run(my_task,2) # 提交任务，并等待结果，相当于 await (await pool.submit(my_task,2))
    
    # await pool.shutdown()  # 如果不用async with创建pool，
    # SmartAioPool 不怕你忘了写await pool.shutdown() 导致还有任务未完成，程序就提前结束了。

asyncio.run(main())
```



## 1.4 使用示例

### 1.4.1 SmartAioPool基本用法

```python
import asyncio
from nb_aiopool import SmartAioPool

async def sample_task(x):
    await asyncio.sleep(0.1)
    return x * 2

async def main():
    # 使用上下文管理器（推荐）
    async with SmartAioPool(max_concurrency=10) as pool:
        # run是提交任务并等待结果，相当于 await (await pool.submit(sample_task, 5))
        result = await pool.run(sample_task, 5)
        print(f"结果: {result}")
        
        # 批量提交任务
        futures = [await pool.submit(sample_task,i) for i in range(20)]
        results = await asyncio.gather(*futures) # 用户手动gather了所有future对象，等待所有任务完成
        print(f"批量结果: {results}")

asyncio.run(main())
```

### 1.4.1.b SmartAioPool 黑科技：自动资源管理

```python
from nb_aiopool import SmartAioPool, smart_run

# 启用自动关机功能
pool = SmartAioPool(auto_shutdown=True)

async def main():
    # 提交任务但不等待
    await pool.submit(sample_task,1)
    await pool.submit(sample_task,2)
    await pool.submit(sample_task,3)
    # 用户没有手动await 返回的future对象，程序会提前退出，导致未完成任务丢失。 
    # 但是使用 SmartAioPool，程序退出时会自动等待所有任务完成

# 使用 smart_run 自动等待所有任务完成，
# 由于SmartAioPool 黑科技实现，你使用asyncio.run运行main()也可以，在程序退出前自动等待所有tasks完成   
smart_run(main())
```

### 1.4.2 NoQueueAioPool 基本用法

`NoQueueAioPool` 是一个高性能的选择，它不使用 `asyncio.Queue`，而是直接通过并发原语控制任务创建。它实现简单，性能出色，但需要用户手动管理任务的完成。

```python
import asyncio
from nb_aiopool import NoQueueAioPool

async def sample_task(x):
    await asyncio.sleep(0.1)
    print(f"Task {x} finished")
    return x * 2

async def main():
    # NoQueueAioPool 不支持 async with 上下文管理器，需要手动管理生命周期
    pool = NoQueueAioPool(max_concurrency=10)
    
    # 批量提交任务
    futures = [await pool.submit(sample_task(i)) for i in range(20)]
    
    # 等待所有任务完成
    results = await asyncio.gather(*futures)
    print(f"批量结果: {results}")
    
    # 使用 run 直接获取结果
    result = await pool.run(sample_task(100))
    print(f"run 的结果: {result}")

    # 如果你提交了任务但没有等待 future，你需要手动调用 wait() 来确保它们执行完毕
    for i in range(20, 25):
        await pool.submit(sample_task(i)) # "即发即忘" 风格的提交
    
    print("等待所有剩余任务完成...")
    await pool.wait() # 等待池中所有任务完成
    print("所有任务已完成。")

asyncio.run(main())
```

### 1.4.3 CommonAioPool基本用法

`CommonAioPool` 是一个经典的基于 `asyncio.Queue` 的并发池。它通过固定数量的后台工作协程（worker）来消费队列中的任务，实现稳定可靠的并发控制。它的实现简单，性能良好，是许多场景下的首选。

```python
import asyncio
from nb_aiopool import CommonAioPool

async def sample_task(x):
    await asyncio.sleep(0.1)
    print(f"Executing task {x}")
    return x * 2

async def main():
    # 推荐使用 async with 上下文管理器，它会自动处理 shutdown
    async with CommonAioPool(max_concurrency=5, max_queue_size=100) as pool:
        # 1. 使用 run 提交任务并直接等待结果
        result = await pool.run(sample_task(100))
        print(f"Run result: {result}")

        # 2. 使用 submit 批量提交任务，返回 future 对象
        futures = [await pool.submit(sample_task(i)) for i in range(10)]
        
        # 等待所有任务完成
        results = await asyncio.gather(*futures)
        print(f"Batch results: {results}")

    # 如果不使用 async with，则需要手动调用 pool.shutdown() 来确保所有任务完成

asyncio.run(main())
```

### 1.4.10 注意 SmartAioPool 和 CommonAioPool 和 NoQueueAioPool 的submit用法区别

这是一个非常重要的区别，如果混淆使用会导致 `TypeError`。

核心区别在于 `submit` 方法接收参数的方式：

-   **`SmartAioPool`**: 遵循 `(函数, *参数)` 的风格，类似于 `concurrent.futures.ThreadPoolExecutor`。
-   **`CommonAioPool` 和 `NoQueueAioPool`**: 遵循更现代的 `asyncio` 风格，直接接收一个**协程对象**。

---

#### 1.4.10.1 `SmartAioPool` 的用法 (`func, *args, **kwargs`)

你需要将可调用对象（函数）和它的参数分开传递。

```python
from nb_aiopool import SmartAioPool

async def my_task(x, y):
    return x + y

pool = SmartAioPool(max_concurrency=5)

# 正确用法：函数和参数分开
future = await pool.submit(my_task, 10, 20) 
```

#### 1.4.10.2 `CommonAioPool` 和 `NoQueueAioPool` 的用法 (`coroutine`)

你需要先调用函数创建协程对象，然后将该对象传递给 `submit`。

```python
from nb_aiopool import CommonAioPool # 或 NoQueueAioPool

pool = CommonAioPool(max_concurrency=5)

# 正确用法：直接传递协程对象
future = await pool.submit(my_task(10, 20))
```

#### 1.4.10.3 解释why ！！！为什么 SmartAioPool是 设计成 await pool.submit(my_task, 10, 20) 形式

解释为什么 `CommonAioPool` 和 `NoQueueAioPool` 设计成 `await pool.submit(my_task(10, 20))` 形式？

这种设计是服务于 `SmartAioPool` 最核心的“黑科技”：**程序退出时自动等待未完成的任务**。

1.  **为了“重生”任务**：当程序退出时（`atexit`钩子触发），`asyncio` 原本的事件循环已经关闭。如果 `SmartAioPool` 保存的是协程对象 `my_task(10, 20)`，这个对象已经和旧循环绑定，无法在新循环中再次运行。

2.  **保存“任务配方”**：因此，`SmartAioPool` 必须保存创建任务的“配方”，也就是 `(函数, *参数)`，即 `(my_task, 10, 20)`。

3.  **实现自动等待**：在程序退出时，`SmartAioPool` 会启动一个全新的事件循环，并使用这些“配方”重新创建并运行所有未完成的任务，确保万无一失。


相比之下，`CommonAioPool` 和 `NoQueueAioPool` 没有这个复杂的自动恢复机制，因此采用了更现代、更符合 `asyncio` 直觉的 `await pool.submit(my_task(10, 20))` 形式。


### 1.4.20 pool.run 和 pool.submit 的区别

简单来说：`submit` 是“提交任务，立即返回凭证（Future）”，而 `run` 是“提交任务，并一直等到结果出来”。

---

#### 1.4.20.1 `pool.submit(...)` -> 返回 `Future` 对象

*   **作用**：将一个任务提交到池中，并**立即返回**一个 `asyncio.Future` 对象。
*   **行为**：非阻塞。它不等待任务的实际执行完成，只负责提交。
*   **获取结果**：你需要稍后通过 `await` 这个返回的 `Future` 对象来获取最终结果。
*   **用途**：适用于需要并发执行大量任务，并在未来某个时间点统一收集结果的场景（例如，与 `asyncio.gather` 配合使用）。

```python
# 1. 提交任务，立即返回 future，不等待 my_task 的 sleep
future = await pool.submit(my_task, 1) 

# 2. 在等待结果之前，可以执行其他操作
print("任务已提交，但我可以先做别的事")

# 3. 在需要结果时，再等待 future
result = await future 
print(f"结果: {result}")
```

#### `pool.run(...)` -> 直接返回结果

*   **作用**：提交一个任务，**并等待它执行完成**，然后直接返回任务的**最终结果**。
*   **行为**：阻塞。它会暂停当前协程，直到提交的任务执行完毕。
*   **获取结果**：直接返回任务的执行结果。如果任务出错，它会直接抛出异常。
*   **等价关系**：`await pool.run(...)` 本质上是 `await (await pool.submit(...))` 的语法糖。
*   **用途**：适用于需要提交单个任务并立即使用其结果的简单场景。

```python
# 提交任务并阻塞等待，直到 my_task 完成并返回结果
result = await pool.run(my_task, 2)
print(f"结果: {result}") # 这里直接就能拿到 my_task 的返回值
```


## 1.5 并发池对比

### 1.5.1 SmartAioPool ：
**优点：** 
1. 自动增加减少协程数量，节制开启新协程（虽然协程创建代价比线程小太多）    
2. 自动在程序退出前自动等待所有任务完成，这是黑科技，是代码中最难实现的   
**缺点：** 
为了实现上面2个优点，导致源码实现极其复杂，一般人写不出来，导致`SmartAioPool`性能也更低。     
对于asyncio 并发池，要实现自动在程序退出前自动等待所有任务完成，比 `concurrent.futures.ThreadPoolExecutor` 并发池要复杂得多。     
因为等到 atexit 钩子触发时，事件循环loop已经关闭，无法直接await loop.run_until_complete(asyncio.gather(*tasks)) 等待所有任务完成。

### 1.5.2 CommonAioPool ：
**优点：** 
1. 简单易用，实现简单粗暴。直接启动并发数个协程，不停地从asyncio.Queue中获取任务并执行。 
2. 性能比 `SmartAioPool` 更好
**缺点：**
1. 不能自动在程序退出前自动等待所有任务完成，这点不如 SmartAioPool 
```
如果用户 不用 async with CommonAioPool 创建并发池，而且忘了调用 shutdown() 方法，
如果只submit，但不await 返回的future对象，程序会提前退出，导致未完成任务丢失。 

这就是相当于你 asyncio.create_task() 创建了大量任务，但忘了 await asyncio.gather(*tasks) 等待所有任务完成，
程序会提前退出，产生悲剧。
```

**CommonAioPool 可以在你的起点协程函数最后调用 await shutdown_all_common_aiopools() 来等待所有任务完成**

### 1.5.3 NoQueueAioPool：
**优点：** 
1. 简单易用，直接创建asyncio.Task对象，没有使用 `asyncio.Queue`
2. 性能高，源码实现简单，性能比 `SmartAioPool` 更好
**缺点：** 
1. 不能自动在程序退出前自动等待所有任务完成,这点不如 SmartAioPool


## 1.6 最后，为什么asyncio 也需要协程并发池？1000并发压测web 1000万次举例

例如1000协程，压测web接口1000万次的需求   

你用 `asyncio.Semaphore(1000)` 来控制1000并发，但是 
`tasks = [asyncio.create_task(make_request(url, session, semaphore)) for _ in range(10000000)]`   
迅速创建1000万tasks，造成内存 cpu loop压力都很大。

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HTTP压力测试工具 - 无池版本（极端愚蠢版）

用于向指定主机和端口发送大量HTTP请求以进行性能测试。
此版本迅速给loop编排1000万个asyncio.Task，极端浪费资源。

此版本用于演示aiopool的价值：
1. 控制task的创建速度，避免瞬间创建大量任务导致内存激增
2. 如果有 aioPool，用户写代码更简单
"""

import asyncio
import aiohttp


async def make_request(url, session, semaphore):
    """发送单个HTTP请求"""
    async with semaphore: # 使用 Semaphore 控制并发数量
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
        await asyncio.gather(*tasks) # 如果你不使用 asyncio.gather(*tasks) 等待所有任务完成，程序会提前退出，导致未完成任务丢失。
        print("执行完成")


if __name__ == "__main__":
    asyncio.run(main())
```

## 许可证

MIT