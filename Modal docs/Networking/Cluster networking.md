# Cluster networking

i6pn (IPv6 private networking) is Modal’s private container-to-container networking solution. It allows users to create clusters of Modal containers which can send network traffic to each other with low latency and high bandwidth (≥ 50Gbps).

Normally, `modal.Function` containers can initiate outbound network connections to the internet but they are not directly addressable by other containers. i6pn-enabled containers, on the other hand, can be directly connected to by other i6pn-enabled containers and this is a key enabler of Modal’s preview `@modal.experimental.clustered` functionality.

You can enable i6pn on any `modal.Function`:

```python
@app.function(i6pn=True)
def hello_private_network():
    import socket

    i6pn_addr = socket.getaddrinfo("i6pn.modal.local", None, socket.AF_INET6)[0][4][0]
    print(i6pn_addr) # fdaa:5137:3ebf:a70:1b9d:3a11:71f2:5f0f
```

In this snippet we see that the i6pn-enabled container is able to retrieve its own IPv6 address by
resolving `i6pn.modal.local`. For this Function container to discover the addresses of _other_ containers,
address sharing must be implemented using an auxiliary data structure, such as a shared `modal.Dict` or `modal.Queue`.

## Private networking

All i6pn network traffic is _Workspace private_.

![i6pn-diagram](https://modal-cdn.com/cdnbot/i6pn-1eksk4vuy_c4c4a0df.webp)

In the image above, Workspace A has subnet `fdaa:1::/48`, while Workspace B has subnet `fdaa:2::/48`.

You’ll notice they share the first 16 bits. This is because the `fdaa::/16` prefix contains all of our private network IPv6 addresses, while each workspace is assigned a random 32-bit identifier when it is created. Together, these form the 48-bit subnet.

The upshot of this is that only containers in the same workspace can see each other and send each other network packets. i6pn networking is secure by default.

## Region boundaries

Modal operates a [global fleet](/docs/guide/region-selection) and allows containers to run on multiple cloud providers and in many regions. i6pn networking is however region-scoped functionality, meaning that only i6pn-enabled containers in the same region can perform network communication.

Modal’s i6pn-enabled primitives such as `@modal.experimental.clustered` automatically restrict container geographic placement and cloud placement to ensure inter-container connectivity.

## Public network access to cluster networking

For cluster networked containers that need to be publicly accessible, you need to expose ports with [modal.Tunnel](/docs/guide/tunnels) because i6pn addresses are not publicly exposed.

Consider having a container setup a Tunnel and act as the gateway to the private cluster networking.
