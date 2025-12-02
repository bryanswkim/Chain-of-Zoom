# Running commands in Sandboxes

Once you have created a Sandbox, you can run commands inside it using the
[`Sandbox.exec`](/docs/reference/modal.Sandbox#exec) method.

```python notest
sb = modal.Sandbox.create(app=my_app)

process = sb.exec("echo", "hello", timeout=3)
print(process.stdout.read())

process = sb.exec("python", "-c", "print(1 + 1)", timeout=3)
print(process.stdout.read())

process = sb.exec(
    "bash",
    "-c",
    "for i in $(seq 1 10); do echo foo $i; sleep 0.1; done",
    timeout=5,
)
for line in process.stdout:
    print(line, end="")

sb.terminate()
```

`Sandbox.exec` returns a [`ContainerProcess`](/docs/reference/modal.container_process#modalcontainer_processcontainerprocess)
object, which allows access to the process's `stdout`, `stderr`, and `stdin`.
The `timeout` parameter ensures that the `exec` command will run for at most
`timeout` seconds.

## Input

The Sandbox and ContainerProcess `stdin` handles are [`StreamWriter`](/docs/reference/modal.io_streams#modalio_streamsstreamwriter)
objects. This object supports flushing writes with both synchronous and asynchronous APIs:

```python notest
import asyncio

sb = modal.Sandbox.create(app=my_app)

p = sb.exec("bash", "-c", "while read line; do echo $line; done")
p.stdin.write(b"foo bar\n")
p.stdin.write_eof()
p.stdin.drain()
p.wait()
sb.terminate()

async def run_async():
    sb = await modal.Sandbox.create.aio(app=my_app)
    p = await sb.exec.aio("bash", "-c", "while read line; do echo $line; done")
    p.stdin.write(b"foo bar\n")
    p.stdin.write_eof()
    await p.stdin.drain.aio()
    await p.wait.aio()
    await sb.terminate.aio()

asyncio.run(run_async())
```

## Output

The Sandbox and ContainerProcess `stdout` and `stderr` handles are [`StreamReader`](/docs/reference/modal.io_streams#modalio_streamsstreamreader)
objects. These objects support reading from the stream in both synchronous and asynchronous manners.
These handles also respect the timeout given to `Sandbox.exec`.

To read from a stream after the underlying process has finished, you can use the `read`
method, which blocks until the process finishes and returns the entire output stream.

```python notest
sb = modal.Sandbox.create(app=my_app)
p = sb.exec("echo", "hello")
print(p.stdout.read())
sb.terminate()
```

To stream output, take advantage of the fact that `stdout` and `stderr` are
iterable:

```python notest
import asyncio

sb = modal.Sandbox.create(app=my_app)

p = sb.exec("bash", "-c", "for i in $(seq 1 10); do echo foo $i; sleep 0.1; done")

for line in p.stdout:
    # Lines preserve the trailing newline character, so use end="" to avoid double newlines.
    print(line, end="")
p.wait()
sb.terminate()

async def run_async():
    sb = await modal.Sandbox.create.aio(app=my_app)
    p = await sb.exec.aio("bash", "-c", "for i in $(seq 1 10); do echo foo $i; sleep 0.1; done")
    async for line in p.stdout:
        # Avoid double newlines by using end="".
        print(line, end="")
    await p.wait.aio()
    await sb.terminate.aio()

asyncio.run(run_async())
```

### Stream types

By default, all streams are buffered in memory, waiting to be consumed by the
client. You can control this behavior with the `stdout` and `stderr` parameters.
These parameters are conceptually similar to the `stdout` and `stderr`
parameters of the [`subprocess`](https://docs.python.org/3/library/subprocess.html#subprocess.DEVNULL) module.

```python notest
from modal.stream_type import StreamType

sb = modal.Sandbox.create(app=my_app)

# Default behavior: buffered in memory.
p = sb.exec(
    "bash",
    "-c",
    "echo foo; echo bar >&2",
    stdout=StreamType.PIPE,
    stderr=StreamType.PIPE,
)
print(p.stdout.read())
print(p.stderr.read())

# Print the stream to STDOUT as it comes in.
p = sb.exec(
    "bash",
    "-c",
    "echo foo; echo bar >&2",
    stdout=StreamType.STDOUT,
    stderr=StreamType.STDOUT,
)
p.wait()

# Discard all output.
p = sb.exec(
    "bash",
    "-c",
    "echo foo; echo bar >&2",
    stdout=StreamType.DEVNULL,
    stderr=StreamType.DEVNULL,
)
p.wait()

sb.terminate()
```
