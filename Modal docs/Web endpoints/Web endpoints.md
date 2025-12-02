# Web endpoints

This guide explains how to set up web endpoints with Modal.

All deployed Modal Functions can be [invoked from any other Python application](/docs/guide/trigger-deployed-functions)
using the Modal client library. We additionally provide multiple ways to expose
your Functions over the web for non-Python clients.

You can [turn any Python function into a web endpoint](#simple-endpoints) with a single line
of code, you can [serve a full app](#serving-asgi-and-wsgi-apps) using
frameworks like FastAPI, Django, or Flask, or you can
[serve anything that speaks HTTP and listens on a port](#non-asgi-web-servers).

Below we walk through each method, assuming you're familiar with web applications outside of Modal.
For a detailed walkthrough of basic web endpoints on Modal aimed at developers new to web applications,
see [this tutorial](/docs/examples/basic_web).

## Simple endpoints

The easiest way to create a web endpoint from an existing Python function is to use the
[`@modal.fastapi_endpoint` decorator](/docs/reference/modal.fastapi_endpoint).

```python
image = modal.Image.debian_slim().pip_install("fastapi[standard]")


@app.function(image=image)
@modal.fastapi_endpoint()
def f():
    return "Hello world!"
```

This decorator wraps the Modal Function in a
[FastAPI application](#how-do-web-endpoints-run-in-the-cloud).

_Note: Prior to v0.73.82, this function was named `@modal.web_endpoint`_.

### Developing with `modal serve`

You can run this code as an ephemeral app, by running the command

```shell
modal serve server_script.py
```

Where `server_script.py` is the file name of your code. This will create an
ephemeral app for the duration of your script (until you hit Ctrl-C to stop it).
It creates a temporary URL that you can use like any other REST endpoint. This
URL is on the public internet.

The `modal serve` command will live-update an app when any of its supporting
files change.

Live updating is particularly useful when working with apps containing web
endpoints, as any changes made to web endpoint handlers will show up almost
immediately, without requiring a manual restart of the app.

### Deploying with `modal deploy`

You can also deploy your app and create a persistent web endpoint in the cloud
by running `modal deploy`:

<Asciinema recordingId="jYpIj1nL6JI9cw4W77GV2l5Wl" />

### Passing arguments to an endpoint

When using `@modal.fastapi_endpoint`, you can add
[query parameters](https://fastapi.tiangolo.com/tutorial/query-params/) which
will be passed to your Function as arguments. For instance

```python
image = modal.Image.debian_slim().pip_install("fastapi[standard]")


@app.function(image=image)
@modal.fastapi_endpoint()
def square(x: int):
    return {"square": x**2}
```

If you hit this with a URL-encoded query string with the `x` parameter present,
the Function will receive the value as an argument:

```
$ curl https://modal-labs--web-endpoint-square-dev.modal.run?x=42
{"square":1764}
```

If you want to use a `POST` request, you can use the `method` argument to
`@modal.fastapi_endpoint` to set the HTTP verb. To accept any valid JSON object,
[use `dict` as your type annotation](https://fastapi.tiangolo.com/tutorial/body-nested-models/?h=dict#bodies-of-arbitrary-dicts)
and FastAPI will handle the rest.

```python
image = modal.Image.debian_slim().pip_install("fastapi[standard]")


@app.function(image=image)
@modal.fastapi_endpoint(method="POST")
def square(item: dict):
    return {"square": item['x']**2}
```

This now creates an endpoint that takes a JSON body:

```
$ curl -X POST -H 'Content-Type: application/json' --data-binary '{"x": 42}' https://modal-labs--web-endpoint-square-dev.modal.run
{"square":1764}
```

This is often the easiest way to get started, but note that FastAPI recommends
that you use
[typed Pydantic models](https://fastapi.tiangolo.com/tutorial/body/) in order to
get automatic validation and documentation. FastAPI also lets you pass data to
web endpoints in other ways, for instance as
[form data](https://fastapi.tiangolo.com/tutorial/request-forms/) and
[file uploads](https://fastapi.tiangolo.com/tutorial/request-files/).

## How do web endpoints run in the cloud?

Note that web endpoints, like everything else on Modal, only run when they need
to. When you hit the web endpoint the first time, it will boot up the container,
which might take a few seconds. Modal keeps the container alive for a short
period in case there are subsequent requests. If there are a lot of requests,
Modal might create more containers running in parallel.

For the shortcut `@modal.fastapi_endpoint` decorator, Modal wraps your function in a
[FastAPI](https://fastapi.tiangolo.com/) application. This means that the
[Image](/docs/guide/images)
your Function uses must have FastAPI installed, and the Functions that you write
need to follow its request and response
[semantics](https://fastapi.tiangolo.com/tutorial). Web endpoint Functions can use
all of FastAPI's powerful features, such as Pydantic models for automatic validation,
typed query and path parameters, and response types.

Here's everything together, combining Modal's abilities to run functions in
user-defined containers with the expressivity of FastAPI:

```python
import modal
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

image = modal.Image.debian_slim().pip_install("fastapi[standard]", "boto3")
app = modal.App(image=image)


class Item(BaseModel):
    name: str
    qty: int = 42


@app.function()
@modal.fastapi_endpoint(method="POST")
def f(item: Item):
    import boto3
    # do things with boto3...
    return HTMLResponse(f"<html>Hello, {item.name}!</html>")
```

This endpoint definition would be called like so:

```bash
curl -d '{"name": "Erik", "qty": 10}' \
    -H "Content-Type: application/json" \
    -X POST https://ecorp--web-demo-f-dev.modal.run
```

Or in Python with the [`requests`](https://pypi.org/project/requests/) library:

```python
import requests

data = {"name": "Erik", "qty": 10}
requests.post("https://ecorp--web-demo-f-dev.modal.run", json=data, timeout=10.0)
```

## Serving ASGI and WSGI apps

You can also serve any app written in an
[ASGI](https://asgi.readthedocs.io/en/latest/) or
[WSGI](https://en.wikipedia.org/wiki/Web_Server_Gateway_Interface)-compatible
web framework on Modal.

ASGI provides support for async web frameworks. WSGI provides support for
synchronous web frameworks.

### ASGI apps - FastAPI, FastHTML, Starlette

For ASGI apps, you can create a function decorated with
[`@modal.asgi_app`](/docs/reference/modal.asgi_app) that returns a reference to
your web app:

```python
image = modal.Image.debian_slim().pip_install("fastapi[standard]")

@app.function(image=image)
@modal.concurrent(max_inputs=100)
@modal.asgi_app()
def fastapi_app():
    from fastapi import FastAPI, Request

    web_app = FastAPI()


    @web_app.post("/echo")
    async def echo(request: Request):
        body = await request.json()
        return body

    return web_app
```

Now, as before, when you deploy this script as a Modal App, you get a URL for
your app that you can hit:

<Asciinema recordingId="fNSKPUK5hiiFgQEx0pDaMCYBg" />

The `@modal.concurrent` decorator enables a single container
to process multiple inputs at once, taking advantage of the asynchronous
event loops in ASGI applications. See [this guide](/docs/guide/concurrent-inputs)
for details.

#### ASGI Lifespan

While we recommend using [`@modal.enter`](https://modal.com/docs/guide/lifecycle-functions#enter) for defining container lifecycle hooks, we also support the [ASGI lifespan protocol](https://asgi.readthedocs.io/en/latest/specs/lifespan.html). Lifespans begin when containers start, typically at the time of the first request. Here's an example using [FastAPI](https://fastapi.tiangolo.com/advanced/events/#lifespan):

```python
import modal

app = modal.App("fastapi-lifespan-app")

image = modal.Image.debian_slim().pip_install("fastapi[standard]")

@app.function(image=image)
@modal.asgi_app()
def fastapi_app_with_lifespan():
    from fastapi import FastAPI, Request

    def lifespan(wapp: FastAPI):
        print("Starting")
        yield
        print("Shutting down")

    web_app = FastAPI(lifespan=lifespan)

    @web_app.get("/")
    async def hello(request: Request):
        return "hello"

    return web_app
```

### WSGI apps - Django, Flask

You can serve WSGI apps using the
[`@modal.wsgi_app`](/docs/reference/modal.wsgi_app) decorator:

```python
image = modal.Image.debian_slim().pip_install("flask")


@app.function(image=image)
@modal.concurrent(max_inputs=100)
@modal.wsgi_app()
def flask_app():
    from flask import Flask, request

    web_app = Flask(__name__)


    @web_app.post("/echo")
    def echo():
        return request.json

    return web_app
```

See [Flask's docs](https://flask.palletsprojects.com/en/2.1.x/deploying/asgi/)
for more information on using Flask as a WSGI app.

Because WSGI apps are synchronous, concurrent inputs will be run on separate
threads. See [this guide](/docs/guide/concurrent-inputs) for details.

## Non-ASGI web servers

Not all web frameworks offer an ASGI or WSGI interface. For example,
[`aiohttp`](https://docs.aiohttp.org/) and [`tornado`](https://www.tornadoweb.org/)
use their own asynchronous network binding, while others like
[`text-generation-inference`](https://github.com/huggingface/text-generation-inference)
actually expose a Rust-based HTTP server running as a subprocess.

For these cases, you can use the
[`@modal.web_server`](/docs/reference/modal.web_server) decorator to "expose" a
port on the container:

```python
@app.function()
@modal.concurrent(max_inputs=100)
@modal.web_server(8000)
def my_file_server():
    import subprocess
    subprocess.Popen("python -m http.server -d / 8000", shell=True)
```

Just like all web endpoints on Modal, this is only run on-demand. The function
is executed on container startup, creating a file server at the root directory.
When you hit the web endpoint URL, your request will be routed to the file
server listening on port `8000`.

For `@web_server` endpoints, you need to make sure that the application binds to
the external network interface, not just localhost. This usually means binding
to `0.0.0.0` instead of `127.0.0.1`.

See our examples of how to serve [Streamlit](/docs/examples/serve_streamlit) and
[ComfyUI](/docs/examples/comfyapp) on Modal.

## Serve many configurations with parametrized functions

Python functions that launch ASGI/WSGI apps or web servers on Modal
cannot take arguments.

One simple pattern for allowing client-side configuration of these web endpoints
is to use [parametrized functions](/docs/guide/parametrized-functions).
Each different choice for the values of the parameters will create a distinct
auto-scaling container pool.

```python
@app.cls()
@modal.concurrent(max_inputs=100)
class Server:
    root: str = modal.parameter(default=".")

    @modal.web_server(8000)
    def files(self):
        import subprocess
        subprocess.Popen(f"python -m http.server -d {self.root} 8000", shell=True)
```

The values are provided in URLs as query parameters:

```bash
curl https://ecorp--server-files.modal.run		# use the default value
curl https://ecorp--server-files.modal.run?root=.cache  # use a different value
curl https://ecorp--server-files.modal.run?root=%2F	# don't forget to URL encode!
```

For details, see [this guide to parametrized functions](/docs/guide/parametrized-functions).

## WebSockets

Functions annotated with `@web_server`, `@asgi_app`, or `@wsgi_app` also support
the WebSocket protocol. Consult your web framework for appropriate documentation
on how to use WebSockets with that library.

WebSockets on Modal maintain a single function call per connection, which can be
useful for keeping state around. Most of the time, you will want to set your
handler function to [allow concurrent inputs](/docs/guide/concurrent-inputs),
which allows multiple simultaneous WebSocket connections to be handled by the
same container.

We support the full WebSocket protocol as per
[RFC 6455](https://www.rfc-editor.org/rfc/rfc6455), but we do not yet have
support for [RFC 8441](https://www.rfc-editor.org/rfc/rfc8441) (WebSockets over
HTTP/2) or [RFC 7692](https://datatracker.ietf.org/doc/html/rfc7692)
(`permessage-deflate` extension). WebSocket messages can be up to 2 MiB each.

## Performance and scaling

If you have no active containers when the web endpoint receives a request, it will
experience a "cold start". Consult the guide page on
[cold start performance](/docs/guide/cold-start) for more information on when
Functions will cold start and advice how to mitigate the impact.

If your Function uses `@modal.concurrent`, multiple requests to the same
endpoint may be handled by the same container. Beyond this limit, additional
containers will start up to scale your App horizontally. When you reach the
Function's limit on containers, requests will queue for handling.

Each workspace on Modal has a rate limit on total operations. For a new account,
this is set to 200 function inputs or web endpoint requests per second, with a
burst multiplier of 5 seconds. If you reach the rate limit, excess requests to
web endpoints will return a
[429 status code](https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/429),
and you'll need to [get in touch](mailto:support@modal.com) with us about
raising the limit.

Web endpoint request bodies can be up to 4 GiB, and their response bodies are
unlimited in size.

## Authentication

Modal offers first-class web endpoint protection via [proxy auth tokens](https://modal.com/docs/guide/webhook-proxy-auth).
Proxy auth tokens protect web endpoints by requiring a key and token combination to be passed
in the `Modal-Key` and `Modal-Secret` headers.
Modal works as a proxy, rejecting requests that aren't authorized to access
your endpoint.

We also support standard techniques for securing web servers.

### Token-based authentication

This is easy to implement in whichever framework you're using. For example, if
you're using `@modal.fastapi_endpoint` or `@modal.asgi_app` with FastAPI, you
can validate a Bearer token like this:

```python
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

import modal

image = modal.Image.debian_slim().pip_install("fastapi[standard]")
app = modal.App("auth-example", image=image)

auth_scheme = HTTPBearer()


@app.function(secrets=[modal.Secret.from_name("my-web-auth-token")])
@modal.fastapi_endpoint()
async def f(request: Request, token: HTTPAuthorizationCredentials = Depends(auth_scheme)):
    import os

    print(os.environ["AUTH_TOKEN"])

    if token.credentials != os.environ["AUTH_TOKEN"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Function body
    return "success!"
```

This assumes you have a [Modal Secret](https://modal.com/secrets) named
`my-web-auth-token` created, with contents `{AUTH_TOKEN: secret-random-token}`.
Now, your endpoint will return a 401 status code except when you hit it with the
correct `Authorization` header set (note that you have to prefix the token with
`Bearer `):

```bash
curl --header "Authorization: Bearer secret-random-token" https://modal-labs--auth-example-f.modal.run
```

### Client IP address

You can access the IP address of the client making the request. This can be used
for geolocation, whitelists, blacklists, and rate limits.

```python
from fastapi import Request

import modal

image = modal.Image.debian_slim().pip_install("fastapi[standard]")
app = modal.App(image=image)


@app.function()
@modal.fastapi_endpoint()
def get_ip_address(request: Request):
    return f"Your IP address is {request.client.host}"
```
