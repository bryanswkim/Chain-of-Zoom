# Input concurrency



As traffic to your application increases, Modal will automatically scale up the
number of containers running your Function:

<div class="flex justify-center"><NoConcurrentInputs /></div>

By default, each container will be assigned one input at a time. Autoscaling
across containers allows your Function to process inputs in parallel. This is
ideal when the operations performed by your Function are CPU-bound.

For some workloads, though, it is inefficient for containers to process inputs
one-by-one. Modal supports these workloads with its _input concurrency_ feature,
which allows individual containers to process multiple inputs at the same time:

<div class="flex justify-center"><WithConcurrentInputs /></div>

When used effectively, input concurrency can reduce latency and lower costs.

## Use cases

Input concurrency can be especially effective for workloads that are primarily
I/O-bound, e.g.:

- Querying a database
- Making external API requests
- Making remote calls to other Modal Functions

For such workloads, individual containers may be able to concurrently process
large numbers of inputs with minimal additional latency. This means that your
Modal application will be more efficient overall, as it won't need to scale
containers up and down as traffic ebbs and flows.

Another use case is to leverage _continuous batching_ on GPU-accelerated
containers. Frameworks such as [vLLM](/docs/examples/llm_inference) can
achieve the benefits of batching across multiple inputs even when those
inputs do not arrive simultaneously (because new batches are formed for each
forward pass of the model).

Note that for CPU-bound workloads, input concurrency will likely not be as
effective (or will even be counterproductive), and you may want to use
Modal's [_dynamic batching_ feature](/docs/guide/dynamic-batching) instead.

## Enabling input concurrency

To enable input concurrency, add the `@modal.concurrent` decorator:

```python
@app.function()
@modal.concurrent(max_inputs=100)
def my_function(input: str):
    ...

```

When using the class pattern, the decorator should be applied at the level of
the _class_, not on individual methods:

```python
@app.cls()
@modal.concurrent(max_inputs=100)
class MyCls:

    @modal.method()
    def my_method(self, input: str):
        ...
```

Because all methods on a class will be served by the same containers, a class
with input concurrency enabled will concurrently run distinct methods in
addition to multiple inputs for the same method.

**Note:** The `@modal.concurrent` decorator was added in v0.73.148 of the Modal
Python SDK. Input concurrency could previously be enabled by setting the
`allow_concurrent_inputs` parameter on the `@app.function` decorator.

## Setting a concurrency target

When using the `@modal.concurrent` decorator, you must always configure the
maximum number of inputs that each container will concurrently process. If
demand exceeds this limit, Modal will automatically scale up more containers.

Additional inputs may need to queue up while these additional containers cold
start. To help avoid degraded latency during scaleup, the `@modal.concurrent`
decorator has a separate `target_inputs` parameter. When set, Modal's autoscaler
will aim for this target as it provisions resources. If demand increases faster
than new containers can spin up, the active containers will be allowed to burst
above the target up to the `max_inputs` limit:

```python
@app.function()
@modal.concurrent(max_inputs=120, target_inputs=100)  # Allow a 20% burst
def my_function(input: str):
    ...
```

It may take some experimentation to find the right settings for these parameters
in your particular application. Our suggestion is to set the `target_inputs`
based on your desired latency and the `max_inputs` based on resource constraints
(i.e., to avoid GPU OOM). You may also consider the relative latency cost of
scaling up a new container versus overloading the existing containers.

## Concurrency mechanisms

Modal uses different concurrency mechanisms to execute your Function depending
on whether it is defined as synchronous or asynchronous. Each mechanism imposes
certain requirements on the Function implementation. Input concurrency is an
advanced feature, and it's important to make sure that your implementation
complies with these requirements to avoid unexpected behavior.

For synchronous Functions, Modal will execute concurrent inputs on separate
threads. _This means that the Function implementation must be thread-safe._

```python
# Each container can execute up to 10 inputs in separate threads
@app.function()
@modal.concurrent(max_inputs=10)
def sleep_sync():
    # Function must be thread-safe
    time.sleep(1)
```

For asynchronous Functions, Modal will execute concurrent inputs using
separate `asyncio` tasks on a single thread. This does not require thread
safety, but it does mean that the Function needs to participate in
collaborative multitasking (i.e., it should not block the event loop).

```python
# Each container can execute up to 10 inputs with separate async tasks
@app.function()
@modal.concurrent(max_inputs=10)
async def sleep_async():
    # Function must not block the event loop
    await asyncio.sleep(1)
```

## Gotchas

Input concurrency is a powerful feature, but there are a few caveats that can
be useful to be aware of before adopting it.

### Input cancellations

Synchronous and asynchronous Functions handle input cancellations differently.
Modal will raise a `modal.exception.InputCancellation` exception in synchronous
Functions and an `asyncio.CancelledError` in asynchronous Functions.

When using input concurrency with a synchronous Function, a single input
cancellation will terminate the entire container. If your workflow depends on
graceful input cancellations, we recommend using an asynchronous
implementation.

### Concurrent logging

The separate threads or tasks that are executing the concurrent inputs will
write any logs to the same stream. This makes it difficult to associate logs
with a specific input, and filtering for a specific function call in Modal's web
dashboard will show logs for all inputs running at the same time.

To work around this, we recommend including a unique identifier in the messages
you log (either your own identifier or the `modal.current_input_id()`) so that
you can use the search functionality to surface logs for a specific input:

```python
@app.function()
@modal.concurrent(max_inputs=10)
async def better_concurrent_logging(x: int):
    logger.info(f"{modal.current_input_id()}: Starting work with {x}")
```
