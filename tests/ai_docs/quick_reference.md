# CommonAioPool 新 API 快速参考

## 快速对比

### 之前 ❌
```python
# 提交任务
await pool.submit(my_func, arg1, arg2, key=value)

# 运行任务
result = await pool.run(my_func, arg1, arg2, key=value)

# 同步提交
future = pool.sync_submit(my_func, arg1, arg2, loop=loop, key=value)
```

### 现在 ✅
```python
# 提交任务
await pool.submit(my_func(arg1, arg2, key=value))

# 运行任务
result = await pool.run(my_func(arg1, arg2, key=value))

# 同步提交
future = pool.sync_submit(my_func(arg1, arg2, key=value), loop=loop)
```

## 核心要点

1. **传递协程对象**，不是函数和参数
2. **每次提交创建新协程**，协程对象不可重用
3. **API 更简洁**，参数直接在函数调用时传递

## 常见模式

### 单个任务
```python
async with CommonAioPool(max_concurrency=10) as pool:
    future = await pool.submit(fetch_data("https://example.com"))
    result = await future
```

### 批量任务
```python
async with CommonAioPool(max_concurrency=10) as pool:
    futures = [await pool.submit(process(i)) for i in range(100)]
    results = await asyncio.gather(*futures)
```

### 直接获取结果
```python
async with CommonAioPool(max_concurrency=10) as pool:
    result = await pool.run(my_task(arg))
```

### 队列满处理
```python
try:
    future = await pool.submit(task(), block=False)
    result = await future
except RuntimeError:
    print("队列满")
```

## 记住

✅ **DO**: `await pool.submit(func(arg))`  
❌ **DON'T**: `await pool.submit(func, arg)`  

✅ **DO**: 每次都创建新协程  
❌ **DON'T**: 重用同一个协程对象  

✅ **DO**: 使用上下文管理器  
❌ **DON'T**: 忘记 `shutdown()`  

## 完整示例

```python
import asyncio
from nb_aiopool.common_aiopool import CommonAioPool

async def fetch(url: str):
    await asyncio.sleep(0.1)
    return f"Data from {url}"

async def main():
    async with CommonAioPool(max_concurrency=5) as pool:
        # 方式1: submit + await
        f1 = await pool.submit(fetch("url1"))
        f2 = await pool.submit(fetch("url2"))
        r1, r2 = await asyncio.gather(f1, f2)
        
        # 方式2: run (直接返回结果)
        r3 = await pool.run(fetch("url3"))
        
        print(r1, r2, r3)

asyncio.run(main())
```

