# Scaling out

Modal makes it trivially easy to scale compute across thousands of containers.
You won't have to worry about your App crashing if it goes viral or need to wait
a long time for your batch jobs to complete.

For the the most part, scaling out will happen automatically, and you won't need
to think about it. But it can be helpful to understand how Modal's autoscaler
works and how you can control its behavior when you need finer control.

## How does autoscaling work on Modal?

Every Modal Function corresponds to an autoscaling pool of containers. The size
of the pool is managed by Modal's autoscaler. The autoscaler will spin up new
containers when there is no capacity available for new inputs, and it will spin
down containers when resources are idling. By default, Modal Functions will
scale to zero when there are no inputs to process.

Autoscaling decisions are made quickly and frequently so that your batch jobs
can ramp up fast and your deployed Apps can respond to any sudden changes in
traffic.

## Configuring autoscaling behavior

Modal exposes a few settings that allow you to configure the autoscaler's
behavior. These settings can be passed to the `@app.function` or `@app.cls`
decorators:

- `max_containers`: The upper limit on containers for the specific Function.
- `min_containers`: The minimum number of containers that should be kept warm,
  even when the Function is inactive.
- `buffer_containers`: The size of the buffer to maintain while the Function is
  active, so that additional inputs will not need to queue for a new container.
- `scaledown_window`: The maximum duration (in seconds) that individual
  containers can remain idle when scaling down.

In general, these settings allow you to trade off cost and latency. Maintaining
a larger warm pool or idle buffer will increase costs but reduce the chance that
inputs will need to wait for a new container to start.

Similarly, a longer scaledown window will let containers idle for longer, which
might help avoid unnecessary churn for Apps that receive regular but infrequent
inputs. Note that containers may not wait for the entire scaledown window before
shutting down if the App is substantially overprovisioned.

## Dynamic autoscaler updates

It's also possible to update the autoscaler settings dynamically (i.e., without redeploying
the App) using the [`Function.update_autoscaler()`](/docs/reference/modal.Function#update_autoscaler)
method:

```python notest
f = modal.Function.from_name("my-app", "f")
f.update_autoscaler(max_containers=100)
```

The autoscaler settings will revert to the configuration in the function
decorator the next time you deploy the App. Or they can be overridden by
further dynamic updates:

```python notest
f.update_autoscaler(min_containers=2, max_containers=10)
f.update_autoscaler(min_containers=4)  # max_containers=10 will still be in effect
```

A common pattern is to run this method in a [scheduled function](/docs/guide/cron)
that adjusts the size of the warm pool (or container buffer) based on the time of day:

```python
@app.function()
def inference_server():
    ...

@app.function(schedule=modal.Cron("0 6 * * *", timezone="America/New_York"))
def increase_warm_pool():
    inference_server.update_autoscaler(min_containers=4)

@app.function(schedule=modal.Cron("0 22 * * *", timezone="America/New_York"))
def decrease_warm_pool():
    inference_server.update_autoscaler(min_containers=0)
```

When you have a [`modal.Cls`](/docs/reference/modal.Cls), `update_autoscaler`
is a method on an _instance_ and will control the autoscaling behavior of
containers serving the Function with that specific set of parameters:

```python notest
MyClass = modal.Cls.from_name("my-app", "MyClass")
obj = MyClass(model_version="3.5")
obj.update_autoscaler(buffer_containers=2)  # type: ignore
```

Note that it's necessary to disable type checking on this line, because the
object will appear as an instance of the class that you defined rather than the
Modal wrapper type.

## Parallel execution of inputs

If your code is running the same function repeatedly with different independent
inputs (e.g., a grid search), the easiest way to increase performance is to run
those function calls in parallel using Modal's
[`Function.map()`](/docs/reference/modal.Function#map) method.

Here is an example if we had a function `evaluate_model` that takes a single
argument:

```python
import modal

app = modal.App()


@app.function()
def evaluate_model(x):
    ...


@app.local_entrypoint()
def main():
    inputs = list(range(100))
    for result in evaluate_model.map(inputs):  # runs many inputs in parallel
        ...
```

In this example, `evaluate_model` will be called with each of the 100 inputs
(the numbers 0 - 99 in this case) roughly in parallel and the results are
returned as an iterable with the results ordered in the same way as the inputs.

### Exceptions

By default, if any of the function calls raises an exception, the exception will
be propagated. To treat exceptions as successful results and aggregate them in
the results list, pass in
[`return_exceptions=True`](/docs/reference/modal.Function#map).

```python
@app.function()
def my_func(a):
    if a == 2:
        raise Exception("ohno")
    return a ** 2

@app.local_entrypoint()
def main():
    print(list(my_func.map(range(3), return_exceptions=True, wrap_returned_exceptions=False)))
    # [0, 1, Exception('ohno'))]
```

Note: prior to version 1.0.5, the returned exceptions inadvertently leaked an internal
wrapper type (`modal.exceptions.UserCodeException`). To avoid breaking any user code that
was checking exception types, we're taking a gradual approach to fixing this bug. Adding
`wrap_returned_exceptions=False` will opt-in to the future default behavior and return the
underlying exception type without a wrapper.

### Starmap

If your function takes multiple variable arguments, you can either use
[`Function.map()`](/docs/reference/modal.Function#map) with one input iterator
per argument, or [`Function.starmap()`](/docs/reference/modal.Function#starmap)
with a single input iterator containing sequences (like tuples) that can be
spread over the arguments. This works similarly to Python's built in `map` and
`itertools.starmap`.

```python
@app.function()
def my_func(a, b):
    return a + b

@app.local_entrypoint()
def main():
    assert list(my_func.starmap([(1, 2), (3, 4)])) == [3, 7]
```

### Gotchas

Note that `.map()` is a method on the modal function object itself, so you don't
explicitly _call_ the function.

Incorrect usage:

```python notest
results = evaluate_model(inputs).map()
```

Modal's map is also not the same as using Python's builtin `map()`. While the
following will technically work, it will execute all inputs in sequence rather
than in parallel.

Incorrect usage:

```python notest
results = map(evaluate_model, inputs)
```

## Asynchronous usage

All Modal APIs are available in both blocking and asynchronous variants. If you
are comfortable with asynchronous programming, you can use it to create
arbitrary parallel execution patterns, with the added benefit that any Modal
functions will be executed remotely. See the [async guide](/docs/guide/async) or
the examples for more information about asynchronous usage.

## GPU acceleration

Sometimes you can speed up your applications by utilizing GPU acceleration. See
the [gpu section](/docs/guide/gpu) for more information.

## Scaling Limits

Modal enforces the following limits for every function:

- 2,000 pending inputs (inputs that haven't been assigned to a container yet)
- 25,000 total inputs (which include both running and pending inputs)

For inputs created with `.spawn()` for async jobs, Modal allows up to 1 million pending inputs instead of 2,000.

If you try to create more inputs and exceed these limits, you'll receive a `Resource Exhausted` error, and you should retry your request later. If you need higher limits, please reach out!

Additionally, each `.map()` invocation can process at most 1000 inputs concurrently.
