# Troubleshooting

## "Command not found" errors

If you installed Modal but you're seeing an error like
`modal: command not found` when trying to run the CLI, this means that the
installation location of Python package executables ("binaries") are not present
on your system path. This is a common problem; you need to reconfigure your
system's environment variables to fix it.

One workaround is to use `python -m modal.cli` instead of `modal`. However, this
is just a patch. There's no single solution for the problem because Python
installs dependencies on different locations depending on your environment. See
this [popular StackOverflow question](https://stackoverflow.com/q/35898734) for
pointers on how to resolve your system path issue.

## Custom types defined in `__main__`

Modal currently uses [cloudpickle](https://github.com/cloudpipe/cloudpickle) to
transfer objects returned or exceptions raised by functions that are executed in
Modal. This gives a lot of flexibility and support for custom data types.

However, any types that are declared in your Python entrypoint file (The one you
call on the command line) will currently be _redeclared_ if they are returned
from Modal functions, and will therefore have the same structure and type name
but not maintain class object identity with your local types. This means that
you _can't_ catch specific custom exception classes:

```python
import modal
app = modal.App()

class MyException(Exception):
    pass

@app.function()
def raise_custom():
    raise MyException()

@app.local_entrypoint()
def main():
    try:
        raise_custom.remote()
    except MyException:  # this will not catch the remote exception
        pass
    except Exception:  # this will catch it instead, as it's still a subclass of Exception
        pass
```

Nor can you do object equality checks on `dataclasses`, or `isinstance` checks:

```python
import modal
import dataclasses

@dataclasses.dataclass
class MyType:
    foo: int

app = modal.App()

@app.function()
def return_custom():
    return MyType(foo=10)


@app.local_entrypoint()
def main():
    data = return_custom.remote()
    assert data == MyType(foo=10)  # false!
    assert data.foo == 10  # true!, the type still has the same fields etc.
    assert isinstance(data, MyType)  # false!
```

If this is a problem for you, you can easily solve it by moving your custom type
definitions to a separate Python file from the one you trigger to run your Modal
code, and import that file instead.

```python
# File: my_types.py
import dataclasses

@dataclasses.dataclass
class MyType:
    foo: int
```

```python notest
# File: modal_script.py
import modal
from my_types import MyType

app = modal.App()

@app.function()
def return_custom():
    return MyType(foo=10)

@app.local_entrypoint()
def main():
    data = return_custom.remote()
    assert data == MyType(foo=10)  # true!
    assert isinstance(data, MyType)  # true!
```

## Function side effects

The same container _can_ be reused for multiple invocations of the same function
within an app. This means that if your function has side effects like modifying
files on disk, they may or may not be present for subsequent calls to that
function. You should not rely on the side effects to be present, but you might
have to be careful so they don't cause problems.

For example, if you create a disk-backed database using sqlite3:

```python
import modal
import sqlite3

app = modal.App()

@app.function()
def db_op():
    db = sqlite3("db_file.sqlite3")
    db.execute("CREATE TABLE example (col_1 TEXT)")
    ...
```

This function _can_ (but will not necessarily) fail on the second invocation
with an

`OperationalError: table foo already exists`

To get around this, take care to either clean up your side effects (e.g.
deleting the db file at the end your function call above) or make your functions
take them into consideration (e.g. adding an
`if os.path.exists("db_file.sqlite")` condition or randomize the filename
above).

## Heartbeat timeout

The Modal client in `modal.Function` containers runs a heartbeat loop that the host uses to healthcheck the container's main process.
If the container stops heartbeating for a long period (minutes) the container will be terminated due to a `heartbeat timeout`, which is displayed in logs.

Container heartbeat timeouts are rare, and typically caused by one of two application-level sources:

- [Global Interpreter Lock](https://wiki.python.org/moin/GlobalInterpreterLock) is held for a long time, stopping the heartbeat thread from making progress. [py-spy](https://github.com/benfred/py-spy?tab=readme-ov-file#how-does-gil-detection-work) can detect GIL holding. We include `py-spy` [automatically in `modal shell`](/docs/guide/developing-debugging#debug-shells) for convenience. A quick fix for GIL holding is to run the code which holds the GIL [in a subprocess](https://docs.python.org/3/library/multiprocessing.html#the-process-class).
- Container process initiates shutdown, intentionally stopping the heartbeats, but it does not complete shutdown.

In both cases [turning on debug logging](/docs/guide/developing-debugging#debug-logs) will help diagnose the issue.

## `413 Content Too Large` errors

If you receive a `413 Content Too Large` error, this might be because you are
hitting our gRPC payload size limits.

The size limit is currently 100MB.

## `403` errors when connecting to GCP services.

GCP will sometimes return 403 errors to Modal when connecting directly to GCP
cloud services like Google Cloud Storage. This is a known issue.

The workaround is to pin the `cloud` parameter in the
[`@app.function`](https://modal.com/docs/reference/modal.App#function) or
[`@app.cls`](https://modal.com/docs/reference/modal.App#cls).

For example:

```python
@app.function(cloud="gcp")
def f():
    ...
```

```python
@app.cls(cloud="gcp")
class MyClass:
    ...
```

## Outdated kernel version (4.4.0)

Our secure runtime [reports a misleadingly old](https://github.com/google/gvisor/issues/11117) kernel version, 4.4.0.
Certain software libraries will detect this and report a warning. These warnings can be ignored because the runtime
actually implements Linux kernel features from versions 5.15+.

If the outdated kernel version reporting creates errors in your application please contact us [in our Slack](https://modal.com/slack).
