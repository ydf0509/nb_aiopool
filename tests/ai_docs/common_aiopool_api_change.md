# CommonAioPool API 变更说明

## 修改日期
2025-10-31

## 概述
将 `CommonAioPool` 的 `submit`、`run` 和 `sync_submit` 方法的入参从 `func, *args, **kwargs` 改为直接接收 `Coroutine` 对象。

## API 变更详情

### 1. `submit` 方法

**之前:**
```python
async def submit(
    self,
    func: Callable[..., Coroutine[Any, Any, T]],
    *args,
    block: bool = True,
    future: asyncio.Future = None,
    **kwargs
) -> asyncio.Future:
    ...
```

**现在:**
```python
async def submit(
    self,
    coro: Coroutine[Any, Any, T],
    block: bool = True,
    future: asyncio.Future = None
) -> asyncio.Future:
    ...
```

**使用示例:**
```python
# 之前
future = await pool.submit(my_async_func, arg1, arg2, kwarg1=value1)

# 现在
future = await pool.submit(my_async_func(arg1, arg2, kwarg1=value1))
```

### 2. `run` 方法

**之前:**
```python
async def run(
    self,
    func: Callable[..., Coroutine[Any, Any, T]],
    *args,
    block: bool = True,
    future: asyncio.Future = None,
    **kwargs
) -> T:
    ...
```

**现在:**
```python
async def run(
    self,
    coro: Coroutine[Any, Any, T],
    block: bool = True,
    future: asyncio.Future = None
) -> T:
    ...
```

**使用示例:**
```python
# 之前
result = await pool.run(my_async_func, arg1, arg2, kwarg1=value1)

# 现在
result = await pool.run(my_async_func(arg1, arg2, kwarg1=value1))
```

### 3. `sync_submit` 方法

**之前:**
```python
def sync_submit(
    self,
    func: Callable[..., Coroutine[Any, Any, T]],
    *args,
    block: bool = True,
    future: asyncio.Future = None,
    loop: asyncio.AbstractEventLoop = None,
    **kwargs
) -> concurrent.futures.Future:
    ...
```

**现在:**
```python
def sync_submit(
    self,
    coro: Coroutine[Any, Any, T],
    block: bool = True,
    future: asyncio.Future = None,
    loop: asyncio.AbstractEventLoop = None
) -> concurrent.futures.Future:
    ...
```

**使用示例:**
```python
# 之前
future = pool.sync_submit(my_async_func, arg1, arg2, loop=loop, kwarg1=value1)

# 现在
future = pool.sync_submit(my_async_func(arg1, arg2, kwarg1=value1), loop=loop)
```

## 内部实现变更

### 1. `_worker` 方法
```python
# 之前
func, args, kwargs, fut = await self._queue.get()
result = await func(*args, **kwargs)

# 现在
coro, fut = await self._queue.get()
result = await coro
```

### 2. `shutdown` 方法
```python
# 之前 - 发送哨兵（4个None）
await self._queue.put((None, None, None, None))

# 现在 - 发送哨兵（2个None）
await self._queue.put((None, None))
```

### 3. 队列数据格式
```python
# 之前
self._queue.put((func, args, kwargs, future))

# 现在
self._queue.put((coro, future))
```

## 修改的文件

1. **`nb_aiopool/common_aiopool.py`**
   - 移除未使用的导入: `Callable`, `from this import s`
   - 修改 `_worker` 方法
   - 修改 `submit` 方法
   - 修改 `run` 方法
   - 修改 `sync_submit` 方法
   - 修改 `shutdown` 方法
   - 更新所有示例代码

2. **`tests/ai_codes/test_common_aiopool.py`** (新建)
   - 完整的测试套件
   - 所有测试通过 ✅

## 优点

1. **更简洁的 API**: 用户直接传递协程对象
2. **类型安全**: 协程对象的类型检查更准确
3. **一致性**: 与其他异步库的使用模式一致
4. **更灵活**: 用户可以在提交前对协程对象进行任何操作

## 注意事项

### 1. 协程对象只能执行一次

```python
# ❌ 错误
coro = my_async_func(1)
await pool.submit(coro)
await pool.submit(coro)  # 错误！协程已被消费

# ✅ 正确
await pool.submit(my_async_func(1))
await pool.submit(my_async_func(1))  # 创建新的协程对象
```

### 2. 批量提交的正确方式

```python
# ✅ 推荐
futures = [await pool.submit(my_async_func(i)) for i in range(10)]

# ⚠️  不推荐（提前创建所有协程）
coros = [my_async_func(i) for i in range(10)]
futures = [await pool.submit(coro) for coro in coros]
```

### 3. 队列满的处理

```python
# 非阻塞模式下，队列满会在 future 中设置异常
try:
    future = await pool.submit(my_async_func(1), block=False)
    result = await future
except RuntimeError as e:
    print(f"队列满: {e}")
```

## 迁移指南

### 基本用法

```python
# 旧代码
await pool.submit(func, arg1, arg2, kwarg=value)
result = await pool.run(func, arg1, arg2, kwarg=value)

# 新代码
await pool.submit(func(arg1, arg2, kwarg=value))
result = await pool.run(func(arg1, arg2, kwarg=value))
```

### 批量提交

```python
# 旧代码
futures = [await pool.submit(func, i) for i in range(100)]

# 新代码
futures = [await pool.submit(func(i)) for i in range(100)]
```

### 上下文管理器

```python
# 旧代码
async with CommonAioPool(max_concurrency=10) as pool:
    await pool.submit(func, arg)

# 新代码
async with CommonAioPool(max_concurrency=10) as pool:
    await pool.submit(func(arg))
```

## 完整示例

```python
import asyncio
from nb_aiopool.common_aiopool import CommonAioPool

async def fetch_data(url: str, timeout: int = 10):
    await asyncio.sleep(0.1)
    return f"Data from {url}"

async def main():
    # 方式1: 手动管理生命周期
    pool = CommonAioPool(max_concurrency=10, max_queue_size=100)
    
    # 提交任务
    future1 = await pool.submit(fetch_data("https://example.com", timeout=5))
    future2 = await pool.submit(fetch_data("https://example.org", timeout=3))
    
    # 等待结果
    result1 = await future1
    result2 = await future2
    print(result1, result2)
    
    # 关闭池
    await pool.shutdown(wait=True)
    
    # 方式2: 使用上下文管理器（推荐）
    async with CommonAioPool(max_concurrency=10, max_queue_size=100) as pool:
        # 批量提交
        urls = ["https://site1.com", "https://site2.com", "https://site3.com"]
        futures = [await pool.submit(fetch_data(url)) for url in urls]
        results = await asyncio.gather(*futures)
        print(results)
    
    # 方式3: 使用 run 直接获取结果
    async with CommonAioPool(max_concurrency=10, max_queue_size=100) as pool:
        result = await pool.run(fetch_data("https://example.net"))
        print(result)

asyncio.run(main())
```

## 测试结果

### 运行测试
```bash
python tests/ai_codes/test_common_aiopool.py
```

### 测试输出
```
🚀 开始测试 CommonAioPool 协程对象 API

==================================================
测试1: submit 接收协程对象
==================================================
✅ 结果: [2, 4, 6]
✅ 测试1通过!

==================================================
测试2: run 接收协程对象
==================================================
✅ 结果: 20, 40, 60
✅ 测试2通过!

==================================================
测试3: 上下文管理器
==================================================
✅ 完成 10 个任务
✅ 测试3通过!

==================================================
测试4: 批量提交协程对象
==================================================
✅ 共完成 20 个任务
✅ 测试4通过!

==================================================
测试5: 错误处理
==================================================
✅ Task 1 结果: 2
✅ Task 2 正确抛出异常: Task 2 failed!
✅ Task 3 结果: 6
✅ 测试5通过!

==================================================
测试6: 队列满处理（非阻塞）
==================================================
✅ 正确处理队列满: Queue full
✅ 完成 5 个任务
✅ 测试6通过!

==================================================
🎉 所有测试通过!
==================================================
```

### Linter 检查
```
No linter errors found. ✅
```

## 结论

✅ 修改成功完成  
✅ 所有测试通过  
✅ 代码质量良好（无 linter 错误）  
✅ API 更简洁直观  

这个变更使得 `CommonAioPool` 的 API 更加现代化和直观，与主流异步编程模式保持一致。

