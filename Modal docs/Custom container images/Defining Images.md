# Images

This guide walks you through how to define a Modal Image, the environment your Modal code runs in.

The typical flow for defining an Image in Modal is
[method chaining](https://jugad2.blogspot.com/2016/02/examples-of-method-chaining-in-python.html)
starting from a base Image, like this:

```python
image = (
    modal.Image.debian_slim(python_version="3.13")
    .apt_install("git")
    .uv_pip_install("torch<3")
    .env({"HALT_AND_CATCH_FIRE": "0"})
    .run_commands("git clone https://github.com/modal-labs/agi && echo 'ready to go!'")
)
```

If you have your own container image defintions, like a Dockerfile or a registry link, you can use those too!
See [this guide](/docs/guide/existing-images).

This page is a high-level guide to using Modal Images.
For reference documentation on the `modal.Image` object, see
[this page](/docs/reference/modal.Image).

## What are Images?

Your code on Modal runs in _containers_. Containers are like light-weight
virtual machines -- container engines use
[operating system tricks](https://earthly.dev/blog/chroot/) to isolate programs
from each other ("containing" them), making them work as though they were
running on their own hardware with their own filesystem. This makes execution
environments more reproducible, for example by preventing accidental
cross-contamination of environments on the same machine. For added security,
Modal runs containers using the sandboxed
[gVisor container runtime](https://cloud.google.com/blog/products/identity-security/open-sourcing-gvisor-a-sandboxed-container-runtime).

Containers are started up from a stored "snapshot" of their filesystem state
called an _image_. Producing the image for a container is called _building_ the
image.

By default, Modal Functions and Sandboxes run in a
[Debian Linux](https://en.wikipedia.org/wiki/Debian) container with a basic
Python installation of the same minor version `v3.x` as your local Python
interpreter.

To make your Apps and Functions useful, you will probably need some third party system packages
or Python libraries. Modal provides a number of options to customize your container images at
different levels of abstraction and granularity, from high-level convenience
methods like `pip_install` through wrappers of core container image build
features like `RUN` and `ENV`. We'll cover each of these in this guide,
along with tips and tricks for building Images effectively when using each tool.

## Add Python packages

The simplest and most common Image modification is to add a third party
Python package, like [`pandas`](https://pandas.pydata.org/).

You can add Python packages to the environment by passing all the packages you
need to the [`Image.uv_pip_install`](/docs/reference/modal.Image#uv_pip_install) method,
which installs packages with [`uv`](https://docs.astral.sh/uv/):

```python
import modal

datascience_image = (
    modal.Image.debian_slim()
    .uv_pip_install("pandas==2.2.0", "numpy")
)


@app.function(image=datascience_image)
def my_function():
    import pandas as pd
    import numpy as np

    df = pd.DataFrame()
    ...
```

You can include
[Python dependency version specifiers](https://peps.python.org/pep-0508/),
like `"torch<3"`, in the arguments. But we recommend pinning dependencies
tightly, like `"torch==2.8.0"`, to improve the reproducibility and robustness
of your builds.

If you run into any issues with
[`Image.uv_pip_install`](/docs/reference/modal.Image#uv_pip_install), then
you can fallback to [`Image.pip_install`](/docs/reference/modal.Image#pip_install) which
uses standard [`pip`](https://pip.pypa.io/en/stable/user_guide/):

```python
datascience_image = (
    modal.Image.debian_slim(python_version="3.13")
    .pip_install("pandas==2.2.0", "numpy")
)
```

Note that because you can define a different environment for each and every
function if you so choose, you don't need to worry about virtual
environment management. Containers make for much better separation of concerns!

If you want to run a specific version of Python remotely rather than just
matching the one you're running locally, provide the `python_version` as a
string when constructing the base image, like we did above.

## Add local files with `add_local_dir` and `add_local_file`

Sometimes your containers need a dependency that's not available on the Internet,
like configuration files or code on your laptop.

To forward files from your local system use the
`image.add_local_dir` and `image.add_local_file` Image methods.

```python
image = modal.Image.debian_slim().add_local_dir("/user/erikbern/.aws", remote_path="/root/.aws")
```

By default, these files are added to your container as it starts up rather than introducing
a new Image layer. This means that the redeployment after making changes is really quick, but
also means you can't run additional build steps after. You can specify a `copy=True` argument
to the `add_local_` methods to instead force the files to be included in the built Image.

### Add local Python code with `add_local_python_source`

You can add Python code that's importable locally to your container
by providing the module name to
[`Image.add_local_python_source`](/docs/reference/modal.Image#add_local_python_source).

```python
image_with_module = modal.Image.debian_slim().add_local_python_source("local_module")

@app.function(image=image_with_module)
def f():
    import local_module

    local_module.do_stuff()
```

The difference from `add_local_dir` is that `add_local_python_source` takes module names as arguments
instead of a file system path and looks up the local package's or module's location via Python's importing
mechanism. The files are then added to directories that make them importable in containers in the
same way as they are locally.

This is intended for pure Python auxiliary modules that are part of your project and that your code imports.
Third party packages should be installed via
[`Image.uv_pip_install`](/docs/reference/modal.Image#uv_pip_install) or similar.

### What if I have different Python packages locally and remotely?

You might want to use packages inside your Modal code that you don't have on
your local computer. In the example above, we build a container that uses
`pandas`. But if we don't have `pandas` locally, on the computer building the
Modal App, we can't put `import pandas` at the top of the script, since it would
cause an `ImportError`.

The easiest solution to this is to put `import pandas` in the function body
instead, as you can see above. This means that `pandas` is only imported when
running inside the remote Modal container, which has `pandas` installed.

Be careful about what you return from Modal Functions that have different
packages installed than the ones you have locally! Modal Functions return Python
objects, like `pandas.DataFrame`s, and if your local machine doesn't have
`pandas` installed, it won't be able to handle a `pandas` object (the error
message you see will mention
[serialization](https://hazelcast.com/glossary/serialization/)/[deserialization](https://hazelcast.com/glossary/deserialization/)).

If you have a lot of Functions and a lot of Python packages, you might want to
keep the imports in the global scope so that every function can use the same
imports. In that case, you can use the
[`Image.imports`](/docs/reference/modal.Image#imports) context manager:

```python
pandas_image = modal.Image.debian_slim().pip_install("pandas", "numpy")


with pandas_image.imports():
    import pandas as pd
    import numpy as np


@app.function(image=pandas_image)
def my_function():
    df = pd.DataFrame()
    ...
```

Because these imports happen before a new container processes its first input,
you can combine this decorator with [memory snapshots](/docs/guide/memory-snapshot)
to improve [cold start performance](/docs/guide/cold-start#share-initialization-work-across-cold-starts-with-memory-snapshots)
for Functions that frequently scale from zero.

## Install system packages with `.apt_install`

You can install Linux packages with the [`apt` package manager](https://www.debian.org/doc/manuals/apt-guide/index.en.html)
using [`Image.apt_install`](/docs/reference/modal.Image#apt_install):

```python
image = modal.Image.debian_slim().apt_install("git", "curl")
```

## Set environment variables with `.env`

You can change the environment variables that your code sees
(in, e.g., [`os.environ`](https://docs.python.org/3/library/os.html#os.environ))
by passing a dictionary to [`Image.env`](/docs/reference/modal.Image#env):

```python
image = modal.Image.debian_slim().env({"PORT": "6443"})
```

Environment variable names and values must be strings.

## Run shell commands with `.run_commands`

You can supply shell commands that should be executed when building the
Image to [`Image.run_commands`](/docs/reference/modal.Image#run_commands):

```python
image_with_repo = (
    modal.Image.debian_slim().apt_install("git").run_commands(
        "git clone https://github.com/modal-labs/gpu-glossary"
    )
)
```

## Run a Python function during your build with `.run_function`

You can run Python code as a build step using the
[`Image.run_function`](/docs/reference/modal.Image#run_function) method.

For example, you can use this to download model parameters from Hugging Face into
your Image:

```python
import os

def download_models() -> None:
    import diffusers

    model_name = "segmind/small-sd"
    pipe = diffusers.StableDiffusionPipeline.from_pretrained(
        model_name, use_auth_token=os.environ["HF_TOKEN"]
    )

hf_cache = modal.Volume.from_name("hf-cache")

image = (
    modal.Image.debian_slim()
        .pip_install("diffusers[torch]", "transformers", "ftfy", "accelerate")
        .run_function(
            download_models,
            secrets=[modal.Secret.from_name("huggingface-secret")],
            volumes={"/root/.cache/huggingface": hf_cache},
        )
)
```

For details on storing model weights on Modal, see
[this guide](/docs/guide/model-weights).

Essentially, this is equivalent to running a Modal Function and snapshotting the
resulting filesystem as a new Image. Any kwargs accepted by [`@app.function`](/docs/reference/modal.App#function)
([`Volume`s](/docs/guide/volumes), [`Secret`s](/docs/guide/secrets), specifications of
resources like [GPUs](/docs/guide/gpu)) can be supplied here.

Whenever you change other features of your Image, like the base Image or the
version of a Python package, the Image will automatically be rebuilt the next
time it is used. This is a bit more complicated when changing the contents of
functions. See the
[reference documentation](/docs/reference/modal.Image#run_function) for details.

## Attach GPUs during setup

If a step in the setup of your Image should be run on an instance with
a GPU (e.g., so that a package can query the GPU to set compilation flags), pass the
desired GPU type when defining that step:

```python
image = (
    modal.Image.debian_slim()
    .pip_install("bitsandbytes", gpu="H100")
)
```

## Use `mamba` instead of `pip` with `micromamba_install`

`pip` installs Python packages, but some Python workloads require the
coordinated installation of system packages as well. The `mamba` package manager
can install both. Modal provides a pre-built
[Micromamba](https://mamba.readthedocs.io/en/latest/user_guide/micromamba.html)
base image that makes it easy to work with `micromamba`:

```python
app = modal.App("bayes-pgm")

numpyro_pymc_image = (
    modal.Image.micromamba()
    .micromamba_install("pymc==5.10.4", "numpyro==0.13.2", channels=["conda-forge"])
)


@app.function(image=numpyro_pymc_image)
def sample():
    import pymc as pm
    import numpyro as np

    print(f"Running on PyMC v{pm.__version__} with JAX/numpyro v{np.__version__} backend")
    ...
```

## Image caching and rebuilds

Modal uses the definition of an Image to determine whether it needs to be
rebuilt. If the definition hasn't changed since the last time you ran or
deployed your App, the previous version will be pulled from the cache.

Images are cached per layer (i.e., per `Image` method call), and breaking
the cache on a single layer will cause cascading rebuilds for all subsequent
layers. You can shorten iteration cycles by defining frequently-changing
layers last so that the cached version of all other layers can be used.

In some cases, you may want to force an Image to rebuild, even if the
definition hasn't changed. You can do this by adding the `force_build=True`
argument to any of the Image building methods.

```python
image = (
    modal.Image.debian_slim()
    .apt_install("git")
    .pip_install("slack-sdk", force_build=True)
    .run_commands("echo hi")
)
```

As in other cases where a layer's definition changes, both the `pip_install` and
`run_commands` layers will rebuild, but the `apt_install` will not. Remember to
remove `force_build=True` after you've rebuilt the Image, or it will
rebuild every time you run your code.

Alternatively, you can set the `MODAL_FORCE_BUILD` environment variable (e.g.
`MODAL_FORCE_BUILD=1 modal run ...`) to rebuild all images attached to your App.
But note that when you rebuild a base layer, the cache will be invalidated for _all_
Images that depend on it, and they will rebuild the next time you run or deploy
any App that uses that base. If you're debugging an issue with your Image, a better
option might be using `MODAL_IGNORE_CACHE=1`. This will rebuild the Image from the
top without breaking the Image cache or affecting subsequent builds.

## Image builder updates

Because changes to base images will cause cascading rebuilds, Modal is
conservative about updating the base definitions that we provide. But many
things are baked into these definitions, like the specific versions of the Image
OS, the included Python, and the Modal client dependencies.

We provide a separate mechanism for keeping base images up-to-date without
causing unpredictable rebuilds: the "Image Builder Version". This is a workspace
level-configuration that will be used for every Image built in your workspace.
We release a new Image Builder Version every few months but allow you to update
your workspace's configuration when convenient. After updating, your next
deployment will take longer, because your Images will rebuild. You may also
encounter problems, especially if your Image definition does not pin the version
of the third-party libraries that it installs (as your new Image will get the
latest version of these libraries, which may contain breaking changes).

You can set the Image Builder Version for your workspace by going to your
[workspace settings](/settings/image-config). This page also documents the
important updates in each version.
