# Asynchronous API usage

All of the functions in Modal are available in both standard (blocking) and
asynchronous variants. The async interface can be accessed by appending `.aio`
to any function in the Modal API.

For example, instead of `my_modal_function.remote("hello")` in a blocking
context, you can use `await my_modal_function.remote.aio("hello")` to get an
asynchronous coroutine response, for use with Python's `asyncio` library.

```python
import asyncio
import modal

app = modal.App()


@app.function()
async def myfunc():
    ...


@app.local_entrypoint()
async def main():
    # execute 100 remote calls to myfunc in parallel
    await asyncio.gather(*[myfunc.remote.aio() for i in range(100)])
```

This is an advanced feature. If you are comfortable with asynchronous
programming, you can use this to create arbitrary parallel execution patterns,
with the added benefit that any Modal functions will be executed remotely.

## Async functions

Regardless if you use an async runtime (like `asyncio`) in your usage of _Modal
itself_, you are free to define your `app.function`-decorated function bodies
as either async or blocking. Both kinds of definitions will work for remote
Modal function calls from both any context.

An async function can call a blocking function, and vice versa.

```python
@app.function()
def blocking_function():
    return 42


@app.function()
async def async_function():
    x = await blocking_function.remote.aio()
    return x * 10


@app.local_entrypoint()
def blocking_main():
    print(async_function.remote())  # => 420
```

If a function is configured to support multiple concurrent inputs per container,
the behavior varies slightly between blocking and async contexts:

- In a blocking context, concurrent inputs will run on separate Python threads.
  These are subject to the GIL, but they can still lead to race conditions if
  used with non-threadsafe objects.
- In an async context, concurrent inputs are simply scheduled as coroutines on
  the executor thread. Everything remains single-threaded.
