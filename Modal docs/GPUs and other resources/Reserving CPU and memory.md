# Reserving CPU and memory

Each Modal container has a default reservation of 0.125 CPU cores and 128 MiB of memory.
Containers can exceed this minimum if the worker has available CPU or memory.
You can also guarantee access to more resources by requesting a higher reservation.

## CPU cores

If you have code that must run on a larger number of cores, you can
request that using the `cpu` argument. This allows you to specify a
floating-point number of CPU cores:

```python
import modal

app = modal.App()

@app.function(cpu=8.0)
def my_function():
    # code here will have access to at least 8.0 cores
    ...
```

Note that this value corresponds to physical cores, not vCPUs.

Modal also will set several environment variables that control multi-threading
behavior in linear algebra libraries (e.g., `OPENBLAS_NUM_THREADS`,
`OMP_NUM_THREADS`, `MKL_NUM_THREADS`) based on your CPU reservation.

## Memory

If you have code that needs more guaranteed memory, you can request it using the
`memory` argument. This expects an integer number of megabytes:

```python
import modal

app = modal.App()

@app.function(memory=32768)
def my_function():
    # code here will have access to at least 32 GiB of RAM
    ...
```

## How much can I request?

For both CPU and memory, a maximum is enforced at Function creation time to
ensure your containers can be scheduled for execution. Requests exceeding the
maximum will be rejected with an
[`InvalidError`](/docs/reference/modal.exception#modalexceptioninvaliderror).

## Billing

For CPU and memory, you'll be charged based on whichever is higher: your reservation or actual usage.

Disk requests are billed by increasing the memory request at a 20:1 ratio. For example, requesting 500 GiB of disk will increase the memory request to 25 GiB, if it is not already set higher.

## Resource limits

### CPU limits

Modal containers have a default soft CPU limit that is set at 16 physical cores above the CPU request.
Given that the default CPU request is 0.125 cores, the default soft CPU limit is 16.125 cores.
Above this limit, the host will begin to throttle the CPU usage of the container.

You can alternatively set the CPU limit explicitly:

```python
cpu_request = 1.0
cpu_limit = 4.0
@app.function(cpu=(cpu_request, cpu_limit))
def f():
    ...
```

### Memory limits

Modal containers can have a hard memory limit which will 'Out of Memory' (OOM) kill
containers which attempt to exceed the limit. This functionality is useful when a process
has a serious memory leak. You can set the limit and have the container killed to avoid paying
for the leaked GBs of memory.

Specify this limit using the [`memory` parameter](/docs/reference/modal.App#function):

```python
mem_request = 1024
mem_limit = 2048
@app.function(
    memory=(mem_request, mem_limit),
)
def f():
    ...
```

### Disk limits

Running Modal containers have access to many GBs of SSD disk, but the amount
of writes is limited by:

1. The size of the underlying worker's SSD disk capacity
2. A per-container disk quota that is set in the 100s of GBs.

Hitting either limit will cause the container's disk writes to be rejected, which
typically manifests as an `OSError`.

Increased disk sizes can be requested with the [`ephemeral_disk` parameter](/docs/reference/modal.App#function). The maximum
disk size is 3.0 TiB (3,145,728 MiB). Larger disks are intended to be used for [dataset processing](/docs/guide/dataset-ingestion).
