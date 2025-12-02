# GPU Health

Modal constantly monitors host GPU health, draining Workers with critical issues
and surfacing warnings for customer triage.

Application level observability of GPU health is facilitated by [metrics](/docs/guide/gpu-metrics) and event logging to container log streams.

## `[gpu-health]` logging

Containers with attached NVIDIA GPUs are connected to our `gpu-health` monitoring system
and receive event logs which originate from either application software behavior, system software behavior, or hardware failure.

These logs are in the following format: `[gpu-health] [LEVEL] GPU-[UUID]: EVENT_TYPE: MSG`

- `gpu-health`: Name indicating the source is Modal's observability system.
- `LEVEL`: Represents the severity level of the log message.
- `GPU_UUID`: A unique identifier for the GPU device associated with the event, if any.
- `EVENT_TYPE`: The type of event source. Modal monitors for multiple types of errors,
  including Xid, SXid, and uncorrectable ECC. See below for more details.
- `MSG`: The message component is either the original message taken from the event source, or a description provided by Modal of the problem.

## Level

The severity level may be `CRITICAL` or `WARN`. Modal automatically responds to `CRITICAL` level events by draining the underlying Worker and migrating customer containers.
`WARN` level logs may be benign or indication of an application or library bug. No automatic action is taken by our system for warnings.

## Handling Application-level health issues

As noted above, Modal will automatically respond to critical GPU events, but warning level events can still
be associated with application exceptions. Applications should catch exceptions caused by GPU-related faults
and call `modal.experimental.stop_fetching_inputs()`:

<!-- TODO: Migrate snippet to modal.Container when it's shipped. ref: https://modal-com.slack.com/archives/C056CGAANRM/p1756931590088119 -->

```python
import modal.experimental
...

@app.function(gpu="H100")
def demo():
    try:
        ... # code which may hit GPU fault (e.g. illegal memory access)
    except RuntimeError:
        modal.experimental.stop_fetching_inputs()
        return
```

## Xid & SXid

The Xid message is an error report from the NVIDIA driver. The SXid, or "Switch Xid" is a report for the NVSwitch component used in GPU-to-GPU communication, and is thus only relevant in multi-GPU containers.

A classic critical Xid error is the 'fell of the bus' report, code 79. The `gpu-health` event log looks like this:

```
[gpu-health] [CRITICAL] GPU-1234: XID: NVRM: Xid (PCI:0000:c6:00): 79, pid=1101234, name=nvc:[driver], GPU has fallen off the bus.
```

There are over 100 Xid codes and they are of highly varying frequency, severity, and specificity.
[NVIDIA's official documentation](https://docs.nvidia.com/deploy/xid-errors/index.html) provides limited information, so
we maintain our own tabular information below.



<GpuHealthXidTable/>
