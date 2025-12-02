# Filesystem Access

There are multiple options for uploading files to a Sandbox and accessing them
from outside the Sandbox.

## Efficient file syncing

To efficiently upload local files to a Sandbox, you can use the
[`add_local_file`](/docs/reference/modal.Image#add_local_file) and
[`add_local_dir`](/docs/reference/modal.Image#add_local_dir) methods on the
[`Image`](/docs/reference/modal.Image) class:

```python notest
sb = modal.Sandbox.create(
    app=my_app,
    image=modal.Image.debian_slim().add_local_dir(
        local_path="/home/user/my_dir",
        remote_path="/app"
    )
)
p = sb.exec("ls", "/app")
print(p.stdout.read())
p.wait()
```

Alternatively, it's possible to use Modal [Volume](/docs/reference/modal.Volume)s or
[CloudBucketMount](/docs/guide/cloud-bucket-mounts)s. These have the benefit that
files created from inside the Sandbox can easily be accessed outside the
Sandbox.

To efficiently upload files to a Sandbox using a Volume, you can use the
[`batch_upload`](/docs/reference/modal.Volume#batch_upload) method on the
`Volume` class - for instance, using an ephemeral Volume that
will be garbage collected when the App finishes:

```python notest
with modal.Volume.ephemeral() as vol:
    import io
    with vol.batch_upload() as batch:
        batch.put_file("local-path.txt", "/remote-path.txt")
        batch.put_directory("/local/directory/", "/remote/directory")
        batch.put_file(io.BytesIO(b"some data"), "/foobar")

    sb = modal.Sandbox.create(
        volumes={"/cache": vol},
        app=my_app,
    )
    p = sb.exec("cat", "/cache/remote-path.txt")
    print(p.stdout.read())
    p.wait()
    sb.terminate()
```

The caller also can access files created in the Volume from the Sandbox, even after the Sandbox is terminated:

```python notest
with modal.Volume.ephemeral() as vol:
    sb = modal.Sandbox.create(
        volumes={"/cache": vol},
        app=my_app,
    )
    p = sb.exec("bash", "-c", "echo foo > /cache/a.txt")
    p.wait()
    sb.terminate()
    sb.wait(raise_on_termination=False)
    for data in vol.read_file("a.txt"):
        print(data)
```

Alternatively, if you want to persist files between Sandbox invocations (useful
if you're building a stateful code interpreter, for example), you can use create
a persisted `Volume` with a dynamically assigned label:

```python notest
session_id = "example-session-id-123abc"
vol = modal.Volume.from_name(f"vol-{session_id}", create_if_missing=True)
sb = modal.Sandbox.create(
    volumes={"/cache": vol},
    app=my_app,
)
p = sb.exec("bash", "-c", "echo foo > /cache/a.txt")
p.wait()
sb.terminate()
sb.wait(raise_on_termination=False)
for data in vol.read_file("a.txt"):
    print(data)
```

File syncing behavior differs between Volumes and CloudBucketMounts. For
Volumes, files are only synced back to the Volume when the Sandbox terminates.
For CloudBucketMounts, files are synced automatically.

## Filesystem API (Alpha)

If you're less concerned with efficiency of uploads and want a convenient way
to pass data in and out of the Sandbox during execution, you can use our
filesystem API to easily read and write files. The API supports reading
files up to 100 MiB and writes up to 1 GiB in size.

This API is currently in Alpha, and we don't recommend using it for production
workloads.

```python
import modal

app = modal.App.lookup("sandbox-fs-demo", create_if_missing=True)

sb = modal.Sandbox.create(app=app)

with sb.open("test.txt", "w") as f:
    f.write("Hello World\n")

f = sb.open("test.txt", "rb")
print(f.read())
f.close()
```

The filesystem API is similar to Python's built-in [io.FileIO](https://docs.python.org/3/library/io.html#io.FileIO) and supports many of the same methods, including `read`, `readline`, `readlines`, `write`, `flush`, `seek`, and `close`.

We also provide the special methods `replace_bytes` and `delete_bytes`, which may be useful for LLM-generated code.

```python notest
from modal.file_io import delete_bytes, replace_bytes

with sb.open("example.txt", "w") as f:
    f.write("The quick brown fox jumps over the lazy dog")

with sb.open("example.txt", "r+") as f:
    # The quick brown fox jumps over the lazy dog
    print(f.read())

    # The slow brown fox jumps over the lazy dog
    replace_bytes(f, b"slow", start=4, end=9)

    # The slow red fox jumps over the lazy dog
    replace_bytes(f, b"red", start=9, end=14)

    # The slow red fox jumps over the dog
    delete_bytes(f, start=32, end=37)

    f.seek(0)
    print(f.read())

sb.terminate()
```

We additionally provide commands [`mkdir`](/docs/reference/modal.Sandbox#mkdir), [`rm`](/docs/reference/modal.Sandbox#rm), and [`ls`](/docs/reference/modal.Sandbox#ls) to make interacting with the filesystem more ergonomic.

<!-- TODO(WRK-956) -->
<!-- ## File Watching

You can watch files or directories for changes using [`watch`](/docs/reference/modal.Sandbox#watch), which is conceptually similar to [`fsnotify`](https://pkg.go.dev/github.com/fsnotify/fsnotify).

```python notest
from modal.file_io import FileWatchEventType

async def watch(sb: modal.Sandbox):
    event_stream = sb.watch.aio(
        "/watch",
        recursive=True,
        filter=[FileWatchEventType.Create, FileWatchEventType.Modify],
    )
    async for event in event_stream:
        print(event)

async def main():
    app = modal.App.lookup("sandbox-file-watch", create_if_missing=True)
    sb = await modal.Sandbox.create.aio(app=app)
    asyncio.create_task(watch(sb))

    await sb.mkdir.aio("/watch")
    for i in range(10):
        async with await sb.open.aio(f"/watch/bar-{i}.txt", "w") as f:
            await f.write.aio(f"hello-{i}")
``` -->
