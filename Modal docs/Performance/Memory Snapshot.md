# Memory Snapshot

Modal can save the state of your Function's memory right after initialization and restore it directly later, skipping initialization work.

These "memory snapshots" can dramatically improve cold start performance for Modal Functions.

During initialization, your code might read many files from the file system, which is quite expensive.
For example, the `torch` package is [hundreds of MiB](https://pypi.org/project/torch/#files) and requires over 20,000 file operations to load!
Such Functions typically start several times faster with memory snapshots enabled.

The memory snapshot feature has two variants. GPU memory snapshots (alpha) provide full GPU access before the snapshot is taken, while CPU memory snapshots do not.

## CPU Memory Snapshot

CPU memory snapshots capture the state of a container and save it to disk. This saved snapshot can then be used to quickly restore new containers to the exact same state.

### Basic usage

You can enable memory snapshots for your Function with the `enable_memory_snapshot=True` parameter:

```python
@app.function(enable_memory_snapshot=True)
def my_func():
    print("hello")
```

Then deploy the App with `modal deploy`. Memory snapshots are created only for deployed Apps.

When using classes decorated with [`@cls`](/docs/guide/lifecycle-functions), [`@modal.enter()`](/docs/reference/modal.enter) hooks are not included in the snapshot by default. Add `snap=True` to include them:

```python
@app.cls(enable_memory_snapshot=True)
class MyCls:
    @modal.enter(snap=True)
    def load(self):
        ...
```

Any code executed in global scope, such as top-level imports, will also be captured by the memory snapshot.

### CPU memory snapshots for GPU workloads

CPU memory snapshots don't support direct GPU memory capture, but GPU Functions can still benefit
from memory snapshots through a two-stage initialization process. This involves refactoring
your initialization code to run across two separate `@modal.enter` functions: one that runs before
creating the snapshot (`snap=True`), and one that runs after restoring from the
snapshot (`snap=False`). Load model weights onto CPU memory in the `snap=True`
method, and then move the weights onto GPU memory in the `snap=False` method.
Here's an example using the `sentence-transformers` package:

```python
import modal

image = modal.Image.debian_slim().pip_install("sentence-transformers")
app = modal.App("sentence-transformers", image=image)

with image.imports():
    from sentence_transformers import SentenceTransformer

model_vol = modal.Volume.from_name("sentence-transformers-models", create_if_missing=True)

@app.cls(gpu="a10g", volumes={"/models": model_vol}, enable_memory_snapshot=True)
class Embedder:
    model_id = "BAAI/bge-small-en-v1.5"

    @modal.enter(snap=True)
    def load(self):
        # Create a memory snapshot with the model loaded in CPU memory.
        self.model = SentenceTransformer(f"/models/{self.model_id}", device="cpu")

    @modal.enter(snap=False)
    def setup(self):
        self.model.to("cuda")  # Move the model to a GPU!

    @modal.method()
    def run(self, sentences:list[str]):
        embeddings = self.model.encode(sentences, normalize_embeddings=True)
        print(embeddings)

@app.local_entrypoint()
def main():
    Embedder().run.remote(sentences=["what is the meaning of life?"])

if __name__ == "__main__":
    cls = modal.Cls.from_name("sentence-transformers", "Embedder")
    cls().run.remote(sentences=["what is the meaning of life?"])
```

Even without GPU snapshotting, this workaround reduces the time it takes for `Embedder.run`
to startup by about 3x, from ~6 seconds down to just ~2 seconds.

### GPU availability during the memory snapshot phase

If you are using the GPU memory snapshot feature (`enable_gpu_snapshot`), then
GPUs are available within `@enter(snap=True)`.

If you are using memory snapshots _without_ `enable_gpu_snapshot`, then it's important
to note that GPUs will not be available within the `@enter(snap=True)` method.

```python
import modal
app = modal.App(image=modal.Image.debian_slim().pip_install("torch"))
@app.cls(enable_memory_snapshot=True, gpu="A10")
class GPUAvailability:
    @modal.enter(snap=True)
    def no_gpus_available_during_snapshots(self):
        import torch
        print(f"GPUs available: {torch.cuda.is_available()}")  # False

    @modal.enter(snap=False)
    def gpus_available_following_restore(self):
        import torch
        print(f"GPUs available: {torch.cuda.is_available()}")  # True

    @modal.method()
    def demo(self):
        print(f"GPUs available: {torch.cuda.is_available()}") # True
```

### Known limitations

The `torch.cuda` module has multiple functions which, if called during
snapshotting, will initialize CUDA as having zero GPU devices. Such functions
include `torch.cuda.is_available` and `torch.cuda.get_device_capability`.
If you're using a framework that calls these methods during its import phase,
it may not be compatible with memory snapshots. The problem can manifest as
confusing "cuda not available" or "no CUDA-capable device is detected" errors.

We have found that importing PyTorch twice solves the problem in some cases:

```python

@app.cls(enable_memory_snapshot=True, gpu="A10")
class GPUAvailability:
    @modal.enter(snap=True)
    def pre_snap(self):
        import torch
        ...
    @modal.enter(snap=False)
    def post_snap(self):
        import torch   # re-import to re-init GPU availability state
        ...
```

In particular, `xformers` is known to call `torch.cuda.get_device_capability` on
import, so if it is imported during snapshotting it can unhelpfully initialize
CUDA with zero GPUs. The
[workaround](https://github.com/facebookresearch/xformers/issues/1030) for this
is to set the `XFORMERS_ENABLE_TRITON` environment variable to `1` in your `modal.Image`.

```python
image = modal.Image.debian_slim().pip_install("xformers>=0.28")  # for instance
image = image.env({"XFORMERS_ENABLE_TRITON": "1"})
```

## GPU Memory Snapshot

With our experimental GPU memory snapshot feature, we are able to capture the entire GPU state too.
This makes for simpler initialization logic and even faster cold starts.

Pass the additional option `experimental_options={"enable_gpu_snapshot": True}` to your Function or class
to enable GPU snapshotting. These functions have full GPU and CUDA access.

```python
@app.function(
    gpu="a10",
    enable_memory_snapshot=True,
    experimental_options={"enable_gpu_snapshot": True},
)
def my_gpu_func():
    import torch
    print(f"GPUs available: {torch.cuda.is_available()}")  # True
```

Here's what the above `SentenceTransformer` example looks like with GPU memory snapshot enabled:

```python notest
@app.cls(
    gpu="a10g",
    volumes={"/models": model_vol},
    enable_memory_snapshot=True,
    experimental_options={"enable_gpu_snapshot": True}
)
class Embedder:
    model_id = "BAAI/bge-small-en-v1.5"

    @modal.enter(snap=True)
    def load(self):
        # Create a memory snapshot with the model loaded in GPU memory.
        self.model = SentenceTransformer(f"/models/{self.model_id}", device="cuda")
```

To achieve even faster cold starts, we recommend warming up your model by running a few forward passes on sample data
in the `@enter(snap=True)` method.

Refer to the code sample [here](/docs/examples/gpu_snapshot) for a more complete example. Our
[blog post](/blog/gpu-mem-snapshots) also provides more useful details.

### Known limitations

GPU memory snapshots are in _alpha_.
[We've seen](/blog/gpu-mem-snapshots) that they can massively reduce cold boot time
but we are still exploring their limitations. Try it for yourself and let us know how it goes!

#### Compatibility with `torch.compile`

If `torch.compile` is called (either directly or indirectly) during the `@modal.enter(snap=True)` method, creating the snapshot will fail for some models. In some of these cases, setting the [environment variable](/docs/guide/environment_variables) `TORCHINDUCTOR_COMPILE_THREADS` to `1` will solve the issue.

## Memory Snapshot FAQ

### When are snapshots updated?

Redeploying your Function with new configuration (e.g. a [new GPU type](/docs/guide/gpu))
or new code will cause previous snapshots to become obsolete.
Subsequent invocations to the new Function version will automatically create new snapshots with the new configuration and code.

Changes to [Modal Volumes](/docs/guide/volumes) do not cause snapshots to update.
Deleting files in a Volume used during restore will cause restore failures.

### I haven't changed my Function. Why do I still see snapshots being created sometimes?

Modal recaptures snapshots to keep up with the platform's latest runtime and security changes.

Additionally, you may observe your Function being memory
snapshot multiple times during its first few invocations. This happens because
memory snapshots are specific to the underlying worker type that created them (e.g. low-level processor details),
and Modal Functions run across a handful of worker types.

Snapshots may add a small amount of latency to Function initialization.

CPU-only Functions need around 6 snapshots for full coverage, and Functions targeting a specific
GPU (e.g. A100) need 2-3.

### How do snapshots handle randomness?

If your application depends on uniqueness of state, you must evaluate your
Function code and verify that it is resilient to snapshotting operations. For
example, if a variable is randomly initialized and snapshotted, that variable
will be identical after every restore, possibly breaking uniqueness expectations
of the proceeding Function code.
