# Networking and security

Sandboxes are built to be secure-by-default, meaning that a default Sandbox has
no ability to accept incoming network connections or access your Modal resources.

## Networking

Since Sandboxes may run untrusted code, they have options to restrict their network access.
To block all network access, set `block_network=True` on [`Sandbox.create`](/docs/reference/modal.Sandbox#create).

For more fine-grained networking control, a Sandbox's outbound network access
can be restricted using the `cidr_allowlist` parameter. This parameter takes a
list of CIDR ranges that the Sandbox is allowed to access, blocking all other
outbound traffic.

### Connecting to Sandboxes with HTTP and WebSockets

You can make authenticated HTTP and WebSocket requests to a Sandbox by generating
Sandbox Connect Tokens. They work like this:

```python notest
# Start a Sandbox with a server running on port 8080.
sb = modal.Sandbox.create(
    "bash", "-c", "python3 -m http.server 8080",
    app=my_app,
)

# Create a connect token, optionally including arbitrary user metadata.
creds = sb.create_connect_token(user_metadata={"user_id": "foo"})

# Make an HTTP request, passing the token in the Authorization header.
requests.get(creds.url, headers={"Authorization": f"Bearer {creds.token}"})

# You can also put the token in a `_modal_connect_token` query param.
url = f"{creds.url}/?_modal_connect_token={creds.token}"
ws_url = url.replace("https://", "wss://")
with websockets.connect(ws_url) as socket:
    socket.send("Hello world!")
```

The server running on port 8080 in the container will receive an authenticated
request with an unspoofable `X-Verified-User-Data` header whose value is the
JSON-serialized Python dict that was passed as `user_metadata` to the
`create_connect_token()` function. This can be used by the application to
determine access control, for example.

There are a few things to remember with Sandbox Connect Tokens:

1. The server inside the container must be listening on port 8080.
2. The token may be sent in an `Authorization` header, in a `_modal_connect_token`
   query param, or in a `_modal_connect_token` cookie.
3. If `_modal_connect_token` is set as a query param, the resulting response will
   include a `Set-Cookie` header that sets it as a cookie.
4. The `user_metadata` must be JSON-serializable and must be less than 512
   characters after serialization.

### Forwarding ports

While it is recommended to use [Sandbox Connect Tokens](#connecting-to-sandboxes-with-http-and-websockets)
for HTTP requests and WebSocket connections to the container, you can also expose
raw TCP ports to the internet. This is useful if, for example, you want to run a
server inside the Sandbox that expects a raw TCP connection and handles
authentication itself.

Use the `encrypted_ports` and `unencrypted_ports` parameters of `Sandbox.create`
to specify which ports to forward. You can then access the public URL of a tunnel
using the [`Sandbox.tunnels`](/docs/reference/modal.Sandbox#tunnels) method:

```python notest
import requests
import time

sb = modal.Sandbox.create(
    "python",
    "-m",
    "http.server",
    "12345",
    encrypted_ports=[12345],
    app=my_app,
)

tunnel = sb.tunnels()[12345]

time.sleep(1)  # Wait for server to start.

print(f"Connecting to {tunnel.url}...")
print(requests.get(tunnel.url, timeout=5).text)
```

It is also possible to create an encrypted port that uses `HTTP/2` rather than `HTTP/1.1` with the `h2_ports` option. This will return
a URL that you can make H2 (HTTP/2 + TLS) requests to. If you want to run an `HTTP/2` server inside a sandbox, this feature may be useful.
Here is an example:

```python notest
import time

port = 4359
sb = modal.Sandbox.create(
    app=my_app,
    image=my_image,
    h2_ports = [port],
)
p = sb.exec("python", "my_http2_server.py")

tunnel = sb.tunnels()[port]
time.sleep(1)
print(f"Tunnel URL: {tunnel.url}")
```

For more details on how tunnels work, see the [tunnels guide](/docs/guide/tunnels).

## Security model

In a typical Modal Function, the Function code can call other Modal APIs allowing
it to spawn containers, create and destroy Volumes, read from Dicts and Queues, etc.
Sandboxes, by contrast, are isolated from the main Modal workspace. They have no API
access, meaning the blast radius of any malicious code is limited to the Sandbox
environment.

Sandboxes are built on top of [gVisor](https://gvisor.dev/), a container runtime
by Google that provides strong isolation properties. gVisor has custom logic to
prevent Sandboxes from making malicious system calls, giving you stronger isolation
than standard [runc](https://github.com/opencontainers/runc) containers.
