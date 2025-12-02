# Failures and retries

When you call a function over a sequence of inputs with
[Function.map()](/docs/guide/scale#parallel-execution-of-inputs), sometimes
errors can happen during function execution. Exceptions from within the remote
function are propagated to the caller, so you can handle them with a
`try-except` statement (refer to
[section on custom types](https://modal.com/docs/guide/troubleshooting#custom-types-defined-in-__main__)
for more on how to catch user-defined exceptions):

```python
@app.function()
def f(i):
    raise ValueError()

@app.local_entrypoint()
def main():
    try:
        for _ in f.map([1, 2, 3]):
            pass
    except ValueError:
        print("Exception handled")
```

## Function retries

You can configure Modal to automatically retry function failures if you set the
`retries` option when declaring your function:

```python
@app.function(retries=3)
def my_flaky_function():
    pass
```

When used with `Function.map()`, each input is retried up to the max number of
retries specified.

The basic configuration shown provides a fixed 1s delay between retry attempts.
For fine-grained control over retry delays, including exponential backoff
configuration, use [`modal.Retries`](/docs/reference/modal.Retries).

To treat exceptions as successful results and aggregate them in the results list instead, pass in [`return_exceptions=True`](/docs/guide/scale#exceptions).

## Container crashes

If a `modal.Function` container crashes (either on start-up, e.g. while handling imports in global scope, or during execution, e.g. an out-of-memory error), Modal will reschedule the container and any work it was currently assigned.

For [ephemeral apps](/docs/guide/apps#ephemeral-apps), container crashes will be retried until a failure rate is exceeded, after which all pending inputs will be failed and the exception will be propagated to the caller.

For [deployed apps](/docs/guide/apps#deployed-apps), container crashes will be retried indefinitely, so as to not disrupt service. Modal will instead apply a crash-loop backoff and the rate of new container creation for the function will be slowed down. Crash-looping containers are displayed in the app dashboard.
