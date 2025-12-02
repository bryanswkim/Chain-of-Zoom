# Tunnels

Modal allows you to expose live TCP ports on a Modal container. This is done by
creating a _tunnel_ that forwards the port to the public Internet.

```python
import modal

app = modal.App()


@app.function()
def start_app():
    # Inside this `with` block, port 8000 on the container can be accessed by
    # the address at `tunnel.url`, which is randomly assigned.
    with modal.forward(8000) as tunnel:
        print(f"tunnel.url        = {tunnel.url}")
        print(f"tunnel.tls_socket = {tunnel.tls_socket}")
        # ... start some web server at port 8000, using any framework
```

Tunnels are direct connections and terminate TLS automatically. Within a few
milliseconds of container startup, this function prints a message such as:

```
tunnel.url        = https://wtqcahqwhd4tu0.r5.modal.host
tunnel.tls_socket = ('wtqcahqwhd4tu0.r5.modal.host', 443)
```

You can also create tunnels on a [Sandbox](/docs/guide/sandbox-networking#forwarding-ports)
to directly expose the container's ports.

## Build with tunnels

Tunnels are the fastest way to get a low-latency, direct connection to a running
container. You can use them to run live browser applications with **interactive
terminals**, **Jupyter notebooks**, **VS Code servers**, and more.

As a quick example, here is how you would expose a Jupyter notebook:

```python
import os
import secrets
import subprocess

import modal


image = modal.Image.debian_slim().pip_install("jupyterlab")
app = modal.App(image=image)


@app.function()
def run_jupyter():
    token = secrets.token_urlsafe(13)
    with modal.forward(8888) as tunnel:
        url = tunnel.url + "/?token=" + token
        print(f"Starting Jupyter at {url}")
        subprocess.run(
            [
                "jupyter",
                "lab",
                "--no-browser",
                "--allow-root",
                "--ip=0.0.0.0",
                "--port=8888",
                "--LabApp.allow_origin='*'",
                "--LabApp.allow_remote_access=1",
            ],
            env={**os.environ, "JUPYTER_TOKEN": token, "SHELL": "/bin/bash"},
            stderr=subprocess.DEVNULL,
        )
```

When you run the function, it starts Jupyter and gives you the public URL. It's
as simple as that.

All Modal features are supported. If you
[need GPUs](https://modal.com/docs/guide/gpu), pass `gpu=` to the
`@app.function()` decorator. If you
[need more CPUs, RAM](https://modal.com/docs/guide/resources), or to attach
[volumes](https://modal.com/docs/guide/volumes), those
also just work.

### Programmable startup

The tunnel API is completely on-demand, so you can start them as the result of a
web request.

For example, you could make something like Jupyter Hub without leaving Modal,
giving your users their own Jupyter notebooks when they visit a URL:

```python
import modal


image = modal.Image.debian_slim().pip_install("fastapi[standard]")
app = modal.App(image=image)


@app.function(timeout=900)  # 15 minutes
def run_jupyter(q):
    ...  # as before, but return the URL on app.q


@app.function()
@modal.fastapi_endpoint(method="POST")
def jupyter_hub():
    from fastapi import HTTPException
    from fastapi.responses import RedirectResponse

    ...  # do some validation on the secret or bearer token

    if is_valid:
        with modal.Queue.ephemeral() as q:
            run_jupyter.spawn(q)
            url = q.get()
            return RedirectResponse(url, status_code=303)

    else:
        raise HTTPException(401, "Not authenticated")
```

This gives every user who sends a POST request to the web endpoint their own
Jupyter notebook server, on a fully isolated Modal container.

You could do the same with VS Code and get some basic version of an instant,
serverless IDE!

### Advanced: Unencrypted TCP tunnels

By default, tunnels are only exposed to the Internet at a secure random URL, and
connections have automatic TLS (the "S" in HTTPS). However, sometimes you might
need to expose a protocol like an SSH server that goes directly over TCP. In
this case, we have support for _unencrypted_ tunnels:

```python notest
with modal.forward(8000, unencrypted=True) as tunnel:
    print(f"tunnel.tcp_socket = {tunnel.tcp_socket}")
```

Might produce an output like:

```
tunnel.tcp_socket = ('r3.modal.host', 23447)
```

You can then connect over TCP, for example with `nc r3.modal.host 23447`. Unlike
encrypted TLS sockets, these cannot be given a non-guessable, cryptographically
random URL due to how the TCP protocol works, so they are assigned a random port
number instead.

## Pricing

Modal only charges for containers based on
[the resources you use](https://modal.com/pricing). There is no additional
charge for having an active tunnel.

For example, if you start a Jupyter notebook on port 8888 and access it via
tunnel, you can use it for an hour for development (with 0.01 CPUs) and then
actually run an intensive job with 16 CPUs for one minute. The amount you would
be billed for in that hour is 0.01 + 16 \* (1/60) = **0.28 CPUs**, even though
you had access to 16 CPUs without needing to restart your notebook.

## Security

Tunnels are run on Modal's private global network of Internet relays. On
startup, your container will connect to the nearest tunnel so you get the
minimum latency, very similar in performance to a direct connection with the
machine.

This makes them ideal for live debugging sessions, using web-based terminals
like [ttyd](https://github.com/tsl0922/ttyd).

The generated URLs are cryptographically random, but they are also public on the
Internet, so anyone can access your application if they are given the URL.

We do not currently do any detection of requests above L4, so if you are running
a web server, we will not add special proxy HTTP headers or translate HTTP/2.
You're just getting the TLS-encrypted TCP stream directly!
