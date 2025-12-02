# Container lifecycle hooks

Since Modal will reuse the same container for multiple inputs, sometimes you
might want to run some code exactly once when the container starts or exits.

To accomplish this, you need to use Modal's class syntax and the
[`@app.cls`](/docs/reference/modal.App#cls) decorator. Specifically, you'll
need to:

1. Convert your function to a method by making it a member of a class.
2. Decorate the class with `@app.cls(...)` with same arguments you previously
   had for `@app.function(...)`.
3. Instead of the `@app.function` decorator on the original method, use
   `@method` or the appropriate decorator for a
   [web endpoint](#lifecycle-hooks-for-web-endpoints).
4. Add the correct method "hooks" to your class based on your need:
   - `@enter` for one-time initialization (remote)
   - `@exit` for one-time cleanup (remote)

## `@enter`

The container entry handler is called when a new container is started. This is
useful for doing one-time initialization, such as loading model weights or
importing packages that are only present in that image.

To use, make your function a member of a class, and apply the `@enter()`
decorator to one or more class methods:

```python
import modal

app = modal.App()

@app.cls(cpu=8)
class Model:
    @modal.enter()
    def run_this_on_container_startup(self):
        import pickle
        self.model = pickle.load(open("model.pickle"))

    @modal.method()
    def predict(self, x):
        return self.model.predict(x)


@app.local_entrypoint()
def main():
    Model().predict.remote(x=123)
```

When working with an [asynchronous Modal](/docs/guide/async) app, you may use an
async method instead:

```python
import modal

app = modal.App()

@app.cls(memory=1024)
class Processor:
    @modal.enter()
    async def my_enter_method(self):
        self.cache = await load_cache()

    @modal.method()
    async def run(self, x):
        return await do_some_async_stuff(x, self.cache)


@app.local_entrypoint()
async def main():
    await Processor().run.remote(x=123)
```

Note: The `@enter()` decorator replaces the earlier `__enter__` syntax, which
has been deprecated.

## `@exit`

The container exit handler is called when a container is about to exit. It is
useful for doing one-time cleanup, such as closing a database connection or
saving intermediate results. To use, make your function a member of a class, and
apply the `@exit()` decorator:

```python
import modal

app = modal.App()

@app.cls()
class ETLPipeline:
    @modal.enter()
    def open_connection(self):
        import psycopg2
        self.connection = psycopg2.connect(os.environ["DATABASE_URI"])

    @modal.method()
    def run(self):
        # Run some queries
        pass

    @modal.exit()
    def close_connection(self):
        self.connection.close()


@app.local_entrypoint()
def main():
    ETLPipeline().run.remote()
```

Exit handlers are also called when a container is [preempted](/docs/guide/preemption).
The exit handler is given a grace period of 30 seconds to finish, and it will be
killed if it takes longer than that to complete.

## Lifecycle hooks for web endpoints

Modal `@function`s that are [web endpoints](/docs/guide/webhooks) can be
converted to the class syntax as well. Instead of `@modal.method`, simply use
whichever of the web endpoint decorators (`@modal.fastapi_endpoint`,
`@modal.asgi_app` or `@modal.wsgi_app`) you were using before.

```python
from fastapi import Request

import modal

image = modal.Image.debian_slim().pip_install("fastapi")
app = modal.App("web-endpoint-cls", image=image)

@app.cls()
class Model:
    @modal.enter()
    def run_this_on_container_startup(self):
        self.model = pickle.load(open("model.pickle"))

    @modal.fastapi_endpoint()
    def predict(self, request: Request):
        ...
```
