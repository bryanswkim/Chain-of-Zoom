# Preemption

All Modal Functions are subject to preemption by default.
If a preemption event interrupts a running Function, Modal will gracefully terminate
the Function and restart it on the same input.

Preemptions are rare, but it is always possible that your Function is
interrupted. Long-running Functions such as model training Functions should take
particular care to tolerate interruptions, as likelihood of interruption increases
with Function run duration.

## Preparing for interruptions

Design your applications to be fault and preemption tolerant. Modal will send an
interrupt signal to your container when preemption occurs. This will cause the
Function's [exit handler](/docs/guide/lifecycle-functions#exit) to run, which
can perform any cleanup within its grace period.

Other best practices for handling preemptions include:

- Divide long-running operations into small tasks or use checkpoints so that you
  can save your work frequently.
- Ensure preemptible operations are safely retryable (ie. idempotent).

## Non-preemptible Functions

If you require Functions that are guaranteed not to be preempted, you may set the `nonpreemptible`
parameter (available starting in client version v1.2.3) to `True` in the `@app.function()` or `@app.cls()` decorator.
Note that a 3x multiplier will be applied to the [list price](https://modal.com/pricing) for CPU and Memory usage when
`nonpreemptible` is set to `True`.

**Note:** The `nonpreemptible` parameter is not supported for GPU Functions.

## Non-preemptible Sandboxes

Modal Sandboxes are not subject to preemption, except in the case where a `region`, `cloud`, or `gpu`
requirement is specified. This is because of availability and scheduling latency constraints.
