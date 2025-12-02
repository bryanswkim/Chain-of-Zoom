# Project structure

## Apps spanning multiple files

When your project spans multiple files, more care is required to package the
full structure for running or deploying on Modal.

There are two main considerations: (1) ensuring that all of your Functions get
registered to the App, and (2) ensuring that any local dependencies get included
in the Modal container.

Say that you have a simple project that's distributed across three files:

```
src/
├── app.py  # Defines the `modal.App` as a variable named `app`
├── llm.py  # Imports `app` and decorates some functions
└── web.py  # Imports `app` and decorates other functions
```

With this structure, if you deploy using `modal deploy src/app.py`, Modal won't
discover the Functions defined in the other two modules, because they never get
imported.

If you instead run `modal deploy src/llm.py`, Modal will deploy the App with
just the Functions defined in that module.

One option would be to ensure that one module in the project transitively
imports all of the other modules and to point the `modal deploy` CLI at it, but
this approach can lead to an awkard project structure.

### Defining your project as a Python package

A better approach would be to define your project as a Python _package_ and to
use the Modal CLI's "module mode" invocation pattern.

In Python, a package is a directory containing an `__init__.py` file (and
usually some other Python modules). If you have a `src/__init__.py` that
imports all of the member modules, it will ensure that any decorated Functions
contained within them get registered to the App:

```python notest
# Contents of __init__.py
import .app
import .llm
import .web
```

_Important: use *relative* imports (`import .app`) between member modules._

Unfortunately, it's not enough just to set this up and make your deploy command
`modal deploy src/app.py`. Instead, you need to invoke Modal in _module mode_:
`modal deploy -m src.app`. Note the use of the `-m` flag and the module path
(`src.app` instead of `src/app.py`). Akin to `python -m ...`, this incantation
treats the target as a package rather than just a single script.

### App composition

As your project grows in scope, it may become helpful to organize it into
multiple component Apps, rather than having the project defined as one large
monolith. That way, as you iterate during development, you can target a specific
component, which will build faster and avoid any conflicts with concurrent work
on other parts of the project.

Projects set up this way can still be deployed as one unit by using `App.include`.
Say our project from above defines separate Apps in `llm.py` and `web.py` and then
adds a new `deploy.py` file:

```python notest
# Contents of deploy.py
import modal

from .llm import llm_app
from .web import web_app

app = modal.App("full-app").include(llm_app).include(web_app)
```

This lets you run `modal deploy -m src.deploy` to package everything in one
step.

**Note:** Since the multi-file app still has a single namespace for all
functions, it's important to name your Modal functions uniquely across the
project even when splitting it up across files: otherwise you risk some
functions "shadowing" others with the same name.

## Including local dependencies

Another factor to consider is whether Modal will package all of the local
dependencies that your App requires.

Even if your Modal App itself can be contained to a single file, any local
modules that file imports (like, say, a `helpers.py`) also need to be available
in the Modal container.

By default, Modal will automatically include the module or package where a
Function is defined in all containers that run that Function. So if the project
is set up as a package and the helper modules are part of that package, you
should be all set. If you're not using a package setup, or if the local
dependencies are external to your project's package, you'll need to explicitly
include them in the Image, i.e. with `modal.Image.add_local_python_source`.

**Note:** This behavior changed in Modal 1.0. Previously, Modal would
"automount" any local dependencies that were imported by your App source into a
container. This was changed to be more selective to avoid unnecessary inclusion
of large local packages.
