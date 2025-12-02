# Snapshots

Sandboxes support snapshotting, allowing you to save your Sandbox's state
and restore it later. This is useful for:

- Creating custom environments for your Sandboxes to run in
- Backing up your Sandbox's state for debugging
- Running large-scale experiments with the same initial state
- Branching your Sandbox's state to test different code changes independently

## Filesystem Snapshots

Filesystem Snapshots are copies of the Sandbox's filesystem at a given point in time.
These Snapshots are [Images](/docs/reference/modal.Image) and can be used to create
new Sandboxes.

To create a Filesystem Snapshot, you can use the
[`Sandbox.snapshot_filesystem()`](/docs/reference/modal.Sandbox#snapshot_filesystem) method:

```python notest
import modal

app = modal.App.lookup("sandbox-fs-snapshot-test", create_if_missing=True)

sb = modal.Sandbox.create(app=app)
p = sb.exec("bash", "-c", "echo 'test' > /test")
p.wait()
assert p.returncode == 0, "failed to write to file"
image = sb.snapshot_filesystem()
sb.terminate()

sb2 = modal.Sandbox.create(image=image, app=app)
p2 = sb2.exec("bash", "-c", "cat /test")
assert p2.stdout.read().strip() == "test"
sb2.terminate()
```

Filesystem Snapshots are optimized for performance: they are calculated as the difference
from your base image, so only modified files are stored. Restoring a Filesystem Snapshot
utilizes the same infrastructure we use to get fast cold starts for your Sandboxes.

Filesystem Snapshots will generally persist indefinitely.

## Memory Snapshots

[Sandboxes memory snapshots](/docs/guide/sandbox-memory-snapshots) are in early preview.
Contact us if this is something you're interested in!
