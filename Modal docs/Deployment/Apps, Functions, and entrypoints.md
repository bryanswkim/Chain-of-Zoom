# Apps, Functions, and entrypoints

An [`App`](/docs/reference/modal.App) represents an application running on Modal. It groups one or more Functions for atomic deployment and acts as a shared namespace. All Functions and Clses are associated with an
App.

A [`Function`](/docs/reference/modal.Function) acts as an independent unit once it is deployed, and [scales up and down](/docs/guide/scale) independently from other Functions. If there are no live inputs to the Function then by default, no containers will run and your account will not be charged for compute resources, even if the App it belongs to is deployed.

An App can be ephemeral or deployed. You can view a list of all currently running Apps on the [`apps`](/apps) page.

The code for a Modal App defining two separate Functions might look something like this:

```python

import modal

app = modal.App(name="my-modal-app")


@app.function()
def f():
    print("Hello world!")


@app.function()
def g():
    print("Goodbye world!")

```

## Ephemeral Apps

An ephemeral App is created when you use the
[`modal run`](/docs/reference/cli/run) CLI command, or the
[`app.run`](/docs/reference/modal.App#run) method. This creates a temporary
App that only exists for the duration of your script.

Ephemeral Apps are stopped automatically when the calling program exits, or when
the server detects that the client is no longer connected.
You can use
[`--detach`](/docs/reference/cli/run) in order to keep an ephemeral App running even
after the client exits.

By using `app.run` you can run your Modal apps from within your Python scripts:

```python
def main():
    ...
    with app.run():
        some_modal_function.remote()
```

By default, running your app in this way won't propagate Modal logs and progress bar messages. To enable output, use the [`modal.enable_output`](/docs/reference/modal.enable_output) context manager:

```python
def main():
    ...
    with modal.enable_output():
        with app.run():
            some_modal_function.remote()
```

## Deployed Apps

A deployed App is created using the [`modal deploy`](/docs/reference/cli/deploy)
CLI command. The App is persisted indefinitely until you stop it via the
[web UI](/apps) or the [`modal app stop`](/docs/reference/cli/app#modal-app-stop) command. Functions in a deployed App that have an attached
[schedule](/docs/guide/cron) will be run on a schedule. Otherwise, you can
invoke them manually using
[web endpoints or Python](/docs/guide/trigger-deployed-functions).

Deployed Apps are named via the [`App`](/docs/reference/modal.App#modalapp)
constructor. Re-deploying an existing `App` (based on the name) will update it
in place.

## Entrypoints for ephemeral Apps

The code that runs first when you `modal run` an App is called the "entrypoint".

You can register a local entrypoint using the
[`@app.local_entrypoint()`](/docs/reference/modal.App#local_entrypoint)
decorator. You can also use a regular Modal function as an entrypoint, in which
case only the code in global scope is executed locally.

### Argument parsing

If your entrypoint function takes arguments with primitive types, `modal run`
automatically parses them as CLI options. For example, the following function
can be called with `modal run script.py --foo 1 --bar "hello"`:

```python
# script.py

@app.local_entrypoint()
def main(foo: int, bar: str):
    some_modal_function.remote(foo, bar)
```

If you wish to use your own argument parsing library, such as `argparse`, you can instead accept a variable-length argument list for your entrypoint or your function. In this case, Modal skips CLI parsing and forwards CLI arguments as a tuple of strings. For example, the following function can be invoked with `modal run my_file.py --foo=42 --bar="baz"`:

```python
import argparse

@app.function()
def train(*arglist):
    parser = argparse.ArgumentParser()
    parser.add_argument("--foo", type=int)
    parser.add_argument("--bar", type=str)
    args = parser.parse_args(args = arglist)
```

### Manually specifying an entrypoint

If there is only one `local_entrypoint` registered,
[`modal run script.py`](/docs/reference/cli/run) will automatically use it. If
you have no entrypoint specified, and just one decorated Modal function, that
will be used as a remote entrypoint instead. Otherwise, you can direct
`modal run` to use a specific entrypoint.

For example, if you have a function decorated with
[`@app.function()`](/docs/reference/modal.App#function) in your file:

```python
# script.py

@app.function()
def f():
    print("Hello world!")


@app.function()
def g():
    print("Goodbye world!")


@app.local_entrypoint()
def main():
    f.remote()
```

Running [`modal run script.py`](/docs/reference/cli/run) will execute the `main`
function locally, which would call the `f` function remotely. However you can
instead run `modal run script.py::app.f` or `modal run script.py::app.g` to
execute `f` or `g` directly.

## Apps were once Stubs

The `modal.App` class in the client was previously called `modal.Stub`. The
old name was kept as an alias for some time, but from Modal 1.0.0 onwards,
using `modal.Stub` will result in an error.
