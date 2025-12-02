# Parametrized functions

A single Modal Function can be parametrized by a set of arguments, so that each unique combination of arguments will behave like an individual
Modal Function with its own auto-scaling and lifecycle logic.

For example, you might want to have a separate pool of containers for each unique user that invokes your Function. In this scenario, you would
parametrize your Function by a user ID.

To parametrize a Modal Function, you need to use Modal's [class syntax](/docs/guide/lifecycle-functions) and the
[`@app.cls`](/docs/reference/modal.App#cls) decorator. Specifically, you'll need to:

1. Convert your function to a method by making it a member of a class.
2. Decorate the class with `@app.cls(...)` with the same arguments you previously
   had for `@app.function(...)` or your [web endpoint decorator](/docs/guide/webhooks).
3. If you previously used the `@app.function()` decorator on your function, replace it with `@modal.method()`.
4. Define dataclass-style, type-annotated instance attributes with `modal.parameter()` and optionally set default values:

```python
import modal

app = modal.App()

@app.cls()
class MyClass:

    foo: str = modal.parameter()
    bar: int = modal.parameter(default=10)

    @modal.method()
    def baz(self, qux: str = "default") -> str:
        return f"This code is running in container pool ({self.foo}, {self.bar}), with input qux={qux}"
```

The parameters create a keyword-only constructor for your class, and the methods can be called as follows:

```python
@app.local_entrypoint()
def main():
    m1 = MyClass(foo="hedgehog", bar=7)
    m1.baz.remote()

    m2 = MyClass(foo="fox")
    m2.baz.remote(qux="override")
```

Function calls for each unique combination of values for `foo` and `bar` will run in their own separate container pools.
If you re-constructed a `MyClass` with the same arguments in a different context, the calls to `baz` would be routed to the same set of containers as before.

Some things to note:

- The total size of the arguments is limited to 16 KiB.
- Modal classes can still annotate types of regular class attributes, which are independent of parametrization, by either omitting `= modal.parameter()` or using `= modal.parameter(init=False)` to satisfy type checkers.
- The support types are these primitives: `str`, `int`, `bool`, and `bytes`.
- The legacy `__init__` constructor method is being removed, see [the 1.0 migration for details.](/docs/guide/modal-1-0-migration#removing-support-for-custom-cls-constructors)

## Looking up a parametrized function

If you want to call your parametrized function from a Python script running
anywhere, you can use `Cls.lookup`:

```python notest
import modal

MyClass = modal.Cls.from_name("parametrized-function-app", "MyClass")  # returns a class-like object
m = MyClass(foo="snake", bar=12)
m.baz.remote()
```

## Parametrized web endpoints

Modal [web endpoints](/docs/guide/webhooks) can also be parametrized:

```python
app = modal.App("parametrized-endpoint")

@app.cls()
class MyClass():

    foo: str = modal.parameter()
    bar: int = modal.parameter(default=10)

    @modal.fastapi_endpoint()
    def baz(self, qux: str = "default") -> str:
        ...
```

Parameters are specified in the URL as query parameter values.

```bash
curl "https://parametrized-endpoint.modal.run?foo=hedgehog&bar=7&qux=override"
curl "https://parametrized-endpoint.modal.run?foo=hedgehog&qux=override"
curl "https://parametrized-endpoint.modal.run?foo=hedgehog&bar=7"
curl "https://parametrized-endpoint.modal.run?foo=hedgehog"
```

## Using parametrized functions with lifecycle functions

Parametrized functions can be used with [lifecycle functions](/docs/guide/lifecycle-functions).

For example, here is how you might parametrize the [`@enter`](/docs/guide/lifecycle-functions#enter) lifecycle function to load a specific model:

```python
@app.cls()
class Model:

    name: str = modal.parameter()
    size: int = modal.parameter(default=100)

    @modal.enter()
    def load_model(self):
        print(f"Loading model {self.name} with size {self.size}")
        self.model = load_model_util(self.name, self.size)

    @modal.method()
    def generate(self, prompt: str) -> str:
        return self.model.generate(prompt)
```

## Performance

Currently, parametrized Function creation is rate limited to 1 per second, with the ability to burst to 1000. Please [get in touch](mailto:support@modal.com) if you need higher rate limits.
