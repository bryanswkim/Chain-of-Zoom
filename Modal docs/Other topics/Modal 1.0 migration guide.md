# Modal 1.0 migration guide

We released version 1.0 of the Modal Python SDK in May 2025.
This release signifies an increased commitment to API stability and implies
some changes to our development workflow.

Preceding the 1.0 release, we introduced a number of deprecations and changes
based on feedback that we received from early users. These changes were intended
to address pain points and reduce confusion about some aspects of the Modal API.
While adapting to them requires some changes to existing code, we believe that
they’ll make it easier to use Modal going forward.

This page highlights the major changes for 1.0 and provides some advice for how
to migrate your code to the new stable APIs. Most deprecations introduced prior
to the release of v1.0 will not be enforced (actually cause breaking changes)
until a subsequent minor (v1.x) release, but we recommend updating your code so
that you can take advantage of new features and avoid any future issues.

## Deprecating `Image.copy_*` methods

_Introduced in: v0.72.11_

We recently introduced new `Image` methods — `Image.add_local_dir` and
`Image.add_local_file` — to replace the existing `Image.copy_local_dir` and
`Image.copy_local_file`.

The new methods subsume the functionality of the old ones, but their default
behavior is different and more performant. By default, files will be mounted to
the container at runtime rather than copied into a new `Image` layer. This can
speed up development substantially when iterating on the contents of the files.

Building a new `Image` layer should be necessary only when subsequent build
steps will use the added files. In that case, you can pass `copy=True` in
`Image.add_local_file` or `Image.add_local_dir`.

The `Image.add_local_dir` method also has an `ignore=` parameter, which you can
use to pass file-matching patterns (using dockerignore rules) or predicate
functions to exclude files.

## Deprecating `Mount` as part of the public API

_Introduced in: v0.72.4_ | _Enforced in: v1.0.0_

Currently, local files can be mounted to the container filesystem either by
including them in the `Image` definition or by passing a `modal.Mount` object
directly to the `App.function` or `App.cls` decorators. As part of the 1.0
release, we are simplifying the container filesystem configuration to be defined
only by the `Image` used for each Function. This implies deprecation of the
following:

- The `mount=` parameter of `App.function` and `App.cls`
- The `context_mount=` parameter of several `modal.Image` methods
- The `Image.copy_mount` method
- The `Mount` object

Code that uses the `mount=` parameter of `App.function` and `App.cls` should be
migrated to pass those files / directories to the `Image` used by that Function
or Cls, i.e. using the `Image.add_local_file`, `Image.add_local_dir`, or
`Image.add_local_python_source` methods:

```python notest
# Mounting local files

# Old way (deprecated)
mount = modal.Mount.from_local_dir("data").add_local_file("config.yaml")
@app.function(image=image, mount=mount)
def f():
    ...

# New way
image = image.add_local_dir("data", "/root/data").add_local_file("config.yaml", "/root/config.yaml")
@app.function(image=image)
def f():
    ...

## Mounting local Python source code

# Old way (deprecated)
mount = modal.Mount.from_local_python_packages("my-lib"))
@app.function(image=image, mount=mount)
def f()
    ...

# New way
image = image.add_local_python_source("my-lib")
@app.function(image=image)
def f(...):
    ...

## Using Image.copy_mount

# Old way (deprecated)
mount = modal.Mount.from_local_dir("data").add_local_file("config.yaml")
image.copy_mount(mount)

# New way
image.add_local_dir("data", "root/data").add_local_file("config.yaml", "/root/config.yaml")
```

Code that uses the `context_mount=` parameter of `Image.from_dockerfile` and
`Image.dockerfile_commands` methods can delete that parameter; we now
automatically infer the files that need to be included in the context.

## Deprecating the `@modal.build` decorator

_Introduced in: v0.72.17_

As part of consolidating the filesystem configuration API, we are also
deprecating the `modal.build` decorator.

For use cases where `modal.build` would previously have been the suggested
approach (e.g., downloading model weights or other large assets to the
container filesystem), we now recommend using a `modal.Volume` instead. The
main advantage of storing weights in a `Volume` instead of an `Image` is that
the weights do not need to be re-downloaded every time you change something else
about the `Image` definition.

Many frameworks, such as Hugging Face, automatically cache downloaded model
weights. When using these frameworks, you just need to ensure that you mount a
`modal.Volume` to the expected location of the framework’s cache:

```python notest
cache_vol = modal.Volume.from_name("hf-hub-cache")
@app.cls(
    image=image.env({"HF_HUB_CACHE": "/cache"}),
    volumes={"/cache": cache_vol},
    ...
)
class Model:
    @modal.enter()
    def load_model(self):
        self.model = ModelClass.from_pretrained(...)
```

For frameworks that don’t support automatic caching, you could write a separate
function to download the weights and write them directly to the Volume, then
`modal run` against this function before you deploy.

In some cases (e.g., if the step runs very quickly), you may wish for the logic
currently decorated with `@modal.build` to continue modifying the Image
filesystem. In that case, you can extract the method as a standalone function
and pass it to `Image.run_function`:

```python notest
def download_weights():
    ...

image = image.run_function(download_weights)
```

## Requiring explicit inclusion of local Python dependencies

_Introduced in: 0.73.11_ | _Enforced in: 1.0.0_

Prior to 1.0, Modal will inspect the modules that are imported when running
your App code and automatically include any "local" modules in the remote
container environment. This behavior is referred to as "automounting".

While convenient, this approach has a number of edge cases and surprising
behaviors, such as ignoring modules with imports that are deferred using
`Image.imports`. Additionally, it is difficult to configure the automounting
behavior to, e.g., ignore large data files that are stored within your local
Python project directories.

Going forward, it will be necessary to explicitly include the local dependencies
of your Modal App. The easiest way to do this is with
[`Image.add_local_python_source`](/docs/reference/modal.Image#add_local_python_source):

```python notest
import modal
import helpers

image = modal.Image.debian_slim().add_local_python_source("helpers")
```

In the period leading up to the change in default behavior, the Modal client
will issue deprecation warnings when automounted modules are not included
in the Image. Updating the Image definition will remove these warnings.

Note that Modal will continue to automatically include the source module or
package defining the App itself. We're introducing a new App or Function-level
parameter, `include_source`, which can be set to `False` in cases where this is
not desired (i.e., because your Image definition already includes the App
source).

## Renaming autoscaler parameters

_Introduced in: v0.73.76_

We're renaming several parameters that configure autoscaling behavior:

- `keep_warm` is now `min_containers`
- `concurrency_limit` is now `max_containers`
- `container_idle_timeout` is now `scaledown_window`

The renaming is intended to address some persistent confusion about
the meaning of these parameters. The migration path is a simple
find-and-replace operation.

Additionally, we're promoting a fourth parameter, `buffer_containers`,
from experimental status (previously `_experimental_buffer_containers`).
Like `min_containers`, `buffer_containers` can help mitigate cold-start
penalties by overprovisioning containers while the Function is active.

## Renaming `modal.web_endpoint` to `modal.fastapi_endpoint`

_Introduced in: v0.73.89_

We're renaming the `modal.web_endpoint` decorator to `modal.fastapi_endpoint`
so that the implicit dependency on FastAPI is more clear. This can be a
simple name substitution in your code as the semantics are otherwise identical.

We may reintroduce a lightweight `modal.web_endpoint` without external
dependencies in the future.

## Replacing `allow_concurrent_inputs` with `@modal.concurrent`

_Introduced in: v0.73.148_

The `allow_concurrent_inputs` parameter is being replaced with a new decorator,
`@modal.concurrent`. The decorator can be applied either to a Function or a Cls.
We're moving the input concurrency feature out of "Beta" status as part of this
change.

The new decorator exposes two distinct parameters: `max_inputs` (the limit
on the number of inputs the Function will concurrently accept) and
`target_inputs` (the level of concurrency targeted by the Modal autoscaler).
The simplest migration path is to replace `allow_concurrent_inputs=N` with
`@modal.concurrent(max_inputs=N)`:

```python notest
# Old way, with a function (deprecated)
@app.function(allow_concurrent_inputs=1000)
def f(...):
    ...

# New way, with a function
@app.function()
@modal.concurrent(max_inputs=1000)
def f(...):
    ...

# Old way, with a class (deprecated)
@app.cls(allow_concurrent_inputs=1000)
class MyCls:
    ...

# New way, with a class
@app.cls()
@modal.concurrent(max_inputs=1000)
class MyCls:
    ...
```

Setting `target_inputs` along with `max_inputs` may benefit performance by
reducing latency during periods where the container pool is scaling up. See the
[input concurrency guide](/docs/guide/concurrent-inputs) for more information.

## Deprecating the `.lookup` method on Modal objects

_Introduced in: v0.72.56_

Most Modal objects can be instantiated through two distinct methods:
`.from_name` and `.lookup`. The redundancy between these methods is a persistent
source of confusion.

The `.from_name` method is lazy: it operates entirely locally and instantiates
only a shell for the object. The local object won’t be associated with its
identity on the Modal server until you interact with it. In contrast, the
`.lookup` method is eager: it triggers a remote call to the Modal server, and it
returns a fully-hydrated object.

Because Modal objects can now be hydrated on-demand, when they are first
used, there is rarely any need to eagerly hydrate. Therefore, we’re deprecating
`.lookup` so that there’s only one obvious way to instantiate objects.

In most cases, the migration is a simple find-and-replace of `.lookup` →
`.from_name`.

One exception is when your code needs to access object metadata, such as its ID,
or a web endpoint's URL. In that case, you can explicitly force hydration of the
object by calling its `.hydrate()` method. There may be other subtle consequences,
such as errors being rasied at a different location if no object exists with the
given name.

## Removing support for custom Cls constructors

_Introduced in: v0.74.0_

Classes decorated with `App.cls` are no longer allowed to have a custom constructor
(`__init__` method). Instead, class parameterization should be exposed using
dataclass-style [`modal.parameter`](/docs/reference/modal.parameter) annotations:

```python notest
# Old way (deprecated)
@app.cls()
class MyCls:
    def __init__(self, name: str = "Bert"):
        self.name = name

# New way
@app.cls()
class MyCls:
    name: str = modal.parameter(default="Bert")
```

Modal will provide a synthetic constructor for classes that use `modal.parameter`.
Arguments to the synthetic constructor must be passed using keywords, so you may
need to update your calling code as well:

```python notest
obj = MyCls(name="Bert")  # name= is now required
```

We're making this change to address some persistent confusion about when
constructors execute for remote calls and what operations are allowed to run in
them. If your custom constructor performs any setup logic beyond storing the
parameter values, you should move it to a method decorated with
`@modal.enter()`.

Additionally, we're reducing the types that we support as class parameters to
a small number of primitives (`str`, `int`, `bool`, and `bytes`).

Limiting class parameterization to primitive types will also allow us to provide
better observability over parameterized class instances in the web dashboard,
CLI, and other contexts where it is not possible to represent arbitrary Python
objects.

If you need to parameterize classes across more complex types, you can implement
your own serialization logic, e.g. using strings as the wire format:

```python notest
@app.cls()
class MyCls:
    param_str: str = modal.parameter()

    @modal.enter()
    def deserialize_parameters(self):
        self.param_obj = SomeComplexType.from_str(self.param_str)
```

We recommend adopting interpretable constructor arguments (i.e., prefer
meaningful strings over pickled bytes) so that you will be able to get the most
benefit from future improvements to parameterized class observability.

## Simplifying Cls lookup patterns

_Introduced in: v0.73.26_

Modal previously supported several different patterns for looking up a `modal.Cls`
and remotely invoking one of its methods:

```python notest
# Documented pattern
MyCls = modal.Cls.from_name("my-app", "MyCls")
obj = MyCls()
obj.some_method.remote(...)

# Alternate pattern: skipping the object instantiation
MyCls = modal.Cls.from_name("my-app", "MyCls")
MyCls.some_method.remote(...)

# Alternate pattern: looking up the method as a Function
f = modal.Function.lookup("my-app", "MyCls.some_method")
f.remote(...)
```

While each pattern could successfully trigger a remote function call, there were
a number of subtle differences in behavior between them.

Going forward, we will only support the first pattern. Making remote calls to a
method on a deployed Cls will require you to (a) look up the object using
`modal.Cls` and (b) instantiate the object before calling its methods.

## Deprecating `modal.gpu` objects

_Introduced in: v0.73.31_

The `modal.gpu` objects are being deprecated; going forward, all GPU resource
configuration should be accomplished using strings.

This should be an easy code substitution, e.g. `gpu=modal.gpu.H100()` can be
replaced with `gpu="H100"`. When using the `count=` parameter of the GPU class,
simply append it to the name with a colon (e.g. `gpu="H100:8"`). In the case of
the `modal.gpu.A100(size="80GB")` variant, the name of the corresponding gpu is
`"A100-80GB"`.

Note that string arguments are case-insensitive, so `"H100"` and `"h100"` are
both accepted.

The main rationale for this change is that it will allow us to introduce new
GPU models in the future without requring users to upgrade their SDK.

## Requiring explicit invocation for module mode

_Introduced in: 0.73.58_

The Modal CLI allows you to reference the source code for your App as either
a file path (e.g. `src/my_app.py`) or as a module name (e.g. `src.my_app`).

As in Python, the choice has some implications for how relative imports are
resolved. To make this more salient, Modal will mirror Python going forwared
and require that you explicitly invoke module mode by passing `-m` on your
command line (e.g., `modal deploy -m src.my_app`).
