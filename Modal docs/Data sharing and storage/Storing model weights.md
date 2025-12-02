# Storing model weights on Modal

Efficiently managing the weights of large models is crucial for optimizing the
build times and startup latency of many ML and AI applications.

Our recommended method for working with model weights is to store them in a Modal [Volume](/docs/guide/volumes),
which acts as a distributed file system, a "shared disk" all of your Modal Functions can access.

## Storing weights in a Modal Volume

To store your model weights in a Volume, you need to either
make the Volume available to a Modal Function that saves the model weights
or upload the model weights into the Volume from a client.

### Saving model weights into a Modal Volume from a Modal Function

If you're already generating the weights on Modal, you just need to
attach the Volume to your Modal Function, making it available for reading and writing:

```python
from pathlib import Path

volume = modal.Volume.from_name("model-weights-vol", create_if_missing=True)
MODEL_DIR = Path("/models")

@app.function(gpu="any", volumes={MODEL_DIR: volume})  # attach the Volume
def train_model(data, config):
    import run_training

    model = run_training(config, data)
    model.save(config, MODEL_DIR)
```

Volumes are attached by including them in a dictionary that maps
a path on the remote machine to a `modal.Volume` object.
They look just like a normal file system, so model weights can be saved to them
without adding any special code.

If the model weights are generated outside of Modal and made available
over the Internet, for example by an open-weights model provider
or your own training job on a dedicated cluster,
you can also download them into a Volume from a Modal Function:

```python continuation
@app.function(volumes={MODEL_DIR: volume})
def download_model(model_id):
    import model_hub

    model_hub.download(model_id, local_dir=MODEL_DIR / model_id)
```

Add [Modal Secrets](/docs/guide/secrets) to access weights that require authentication.

See [below](#storing-weights-from-the-hugging-face-hub-on-modal) for
more on downloading from the popular Hugging Face Hub.

### Uploading model weights into a Modal Volume

Instead of pulling weights into a Modal Volume from inside a Modal Function,
you might wish to push weights into Modal from a client,
like your laptop or a dedicated training cluster.

For that, you can use the `batch_upload` method of
[`modal.Volume`](/docs/reference/modal.Volume)s
via the Modal Python client library:

```python continuation
volume = modal.Volume.from_name("model-weights-vol", create_if_missing=True)

@app.local_entrypoint()
def main(local_path: str, remote_path: str):
    with volume.batch_upload() as upload:
        upload.put_directory(local_path, remote_path)
```

Alternatively, you can upload model weights using the
[`modal volume`](/docs/reference/cli/volume) CLI command:

```bash
modal volume put model-weights-vol path/to/model path/on/volume
```

### Mounting cloud buckets as Modal Volumes

If your model weights are already in cloud storage,
for example in an S3 bucket, you can connect them
to Modal Functions with a `CloudBucketMount`.

See [the guide](/docs/guide/cloud-bucket-mounts) for details.

## Reading model weights from a Modal Volume

You can read weights from a Volume as you would normally read them
from disk, so long as you attach the Volume to your Function.

```python continuation
@app.function(gpu="any", volumes={MODEL_DIR: volume})
def inference(prompt, model_id):
    import load_model

    model = load_model(MODEL_DIR / model_id)
    model.run(prompt)
```

## Storing weights in the Modal Image

It is also possible to store weights in your Function's Modal [Image](/docs/guide/images),
the private file system state that a Function sees when it starts up.
The weights might be downloaded via shell commands with [`Image.run_commands`](/docs/guide/images)
or downloaded using a Python function with [`Image.run_function`](/docs/guide/images).

We recommend storing model weights in a Modal [Volume](/docs/guide/volumes),
as described [above](#storing-weights-in-a-modal-volume). Performance is similar
for the two methods. Volumes are more flexible.
Images are rebuilt when their definition changes, starting from the changed layer,
which increases reproducibility for some builds but leads to unnecessary extra downloads
in most cases.

## Optimizing model weight reads with `@enter`

In the above code samples, weights are loaded from disk into memory each time
the `inference` function is run. This isn't so bad if inference is much
slower than model loading (e.g. it is run on very large datasets)
or if the model loading logic is smart enough to skip reloading.

To guarantee a particular model's weights are only loaded once, you can use the `@enter`
[container lifecycle hook](/docs/guide/lifecycle-functions)
to load the weights only when a new container starts.

```python continuation
MODEL_ID = "some-model-id"

@app.cls(gpu="any", volumes={MODEL_DIR: volume})
class Model:
    @modal.enter()
    def setup(self, model_id=MODEL_ID):
        import load_model

        self.model = load_model(MODEL_DIR, model_id)

    @modal.method()
    def inference(self, prompt):
        return self.model.run(prompt)
```

Note that methods decorated with `@enter` can't be passed dynamic arguments.

If you need to load a single but possibly different model on each container start, you can
[parametrize](/docs/guide/parametrized-functions) your Modal Cls.
Below, we use the `modal.parameter` syntax.

```python continuation
@app.cls(gpu="any", volumes={MODEL_DIR: volume})
class ParametrizedModel:
    model_id: str = modal.parameter()

    @modal.enter()
    def setup(self):
        import load_model

        self.model = load_model(MODEL_DIR, self.model_id)

    @modal.method()
    def inference(self, prompt):
        return self.model.run(prompt)
```

## Storing weights from the Hugging Face Hub on Modal

The [Hugging Face Hub](https://huggingface.co/models) has over 1,000,000 models
with weights available for download.

The snippet below shows some additional tricks for downloading models
from the Hugging Face Hub on Modal.

```python
from typing import Optional
from pathlib import Path

import modal

# create a Volume, or retrieve it if it exists
volume = modal.Volume.from_name("model-weights-vol", create_if_missing=True)
MODEL_DIR = Path("/models")

# define dependencies for downloading model
download_image = (
    modal.Image.debian_slim()
    .pip_install("huggingface_hub[hf_transfer]")  # install fast Rust download client
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1"})  # and enable it
)
app = modal.App()

@app.function(
    volumes={MODEL_DIR.as_posix(): volume},  # "mount" the Volume, sharing it with your function
    image=download_image,  # only download dependencies needed here
)
def download_model(
    repo_id: str = "hf-internal-testing/tiny-random-GPTNeoXForCausalLM",
    revision: Optional[str] = None,  # include a revision to prevent surprises!
):
    from huggingface_hub import snapshot_download

    snapshot_download(repo_id=repo_id, local_dir=MODEL_DIR / repo_id, revision=revision)
    print(f"Model downloaded to {MODEL_DIR / repo_id}")
```
