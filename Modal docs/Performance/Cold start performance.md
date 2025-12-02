# Cold start performance

Modal Functions are run in [containers](/docs/guide/images).

If a container is already ready to run your Function, it will be reused.

If not, Modal spins up a new container.
This is known as a _cold start_,
and it is often associated with higher latency.

There are two sources of increased latency during cold starts:

1. inputs may **spend more time waiting** in a queue for a container
   to become ready or "warm".
2. when an input is handled by the container that just started,
   there may be **extra work that only needs to be done on the first invocation**
   ("initialization").

This guide presents techniques and Modal features for reducing the impact of both queueing
and initialization on observed latencies.

If you are invoking Functions with no warm containers
or if you otherwise see inputs spending too much time in the "pending" state,
you should
[target queueing time for optimization](#reduce-time-spent-queueing-for-warm-containers).

If you see some Function invocations taking much longer than others,
and those invocations are the first handled by a new container,
you should
[target initialization for optimization](#reduce-latency-from-initialization).

## Reduce time spent queueing for warm containers

New containers are booted when there are not enough other warm containers to
to handle the current number of inputs.

For example, the first time you send an input to a Function,
there are zero warm containers and there is one input,
so a single container must be booted up.
The total latency for the input will include
the time it takes to boot a container.

If you send another input right after the first one finishes,
there will be one warm container and one pending input,
and no new container will be booted.

Generalizing, there are two factors that affect the time inputs spend queueing:
the time it takes for a container to boot and become warm (which we solve by booting faster)
and the time until a warm container is available to handle an input (which we solve by having more warm containers).

### Warm up containers faster

The time taken for a container to become warm
and ready for inputs can range from seconds to minutes.

Modal's custom container stack has been heavily optimized to reduce this time.
Containers boot in about one second.

But before a container is considered warm and ready to handle inputs,
we need to execute any logic in your code's global scope (such as imports)
or in any
[`modal.enter` methods](/docs/guide/lifecycle-functions).
So if your boots are slow, these are the first places to work on optimization.

For example, you might be downloading a large model from a model server
during the boot process.
You can instead
[download the model ahead of time](/docs/guide/model-weights),
so that it only needs to be downloaded once.

For models in the tens of gigabytes,
this can reduce boot times from minutes to seconds.

### Run more warm containers

It is not always possible to speed up boots sufficiently.
For example, seconds of added latency to load a model may not
be acceptable in an interactive setting.

In this case, the only option is to have more warm containers running.
This increases the chance that an input will be handled by a warm container,
for example one that finishes an input while another container is booting.

Modal currently exposes [three parameters](/docs/guide/scale) that control how
many containers will be warm: `scaledown_window`, `min_containers`,
and `buffer_containers`.

All of these strategies can increase the resources consumed by your Function
and so introduce a trade-off between cold start latencies and cost.

#### Keep containers warm for longer with `scaledown_window`

Modal containers will remain idle for a short period before shutting down. By
default, the maximum idle time is 60 seconds. You can configure this by setting
the `scaledown_window` on the [`@function`](/docs/reference/modal.App#function)
decorator. The value is measured in seconds, and it can be set anywhere between
two seconds and twenty minutes.

```python
import modal

app = modal.App()

@app.function(scaledown_window=300)
def my_idle_greeting():
    return {"hello": "world"}
```

Increasing the `scaledown_window` reduces the chance that subsequent requests
will require a cold start, although you will be billed for any resources used
while the container is idle (e.g., GPU reservation or residual memory
occupancy). Note that containers will not necessarily remain alive for the
entire window, as the autoscaler will scale down more agressively when the
Function is substantially over-provisioned.

#### Overprovision resources with `min_containers` and `buffer_containers`

Keeping already warm containers around longer doesn't help if there are no warm
containers to begin with, as when Functions scale from zero.

To keep some containers warm and running at all times, set the `min_containers`
value on the [`@function`](/docs/reference/modal.App#function) decorator. This
puts a floor on the the number of containers so that the Function doesn't scale
to zero. Modal will still scale up and spin down more containers as the
demand for your Function fluctuates above the `min_containers` value, as usual.

While `min_containers` overprovisions containers while the Function is idle,
`buffer_containers` provisions extra containers while the Function is active.
This "buffer" of extra containers will be idle and ready to handle inputs if
the rate of requests increases. This parameter is particularly useful for
bursty request patterns, where the arrival of one input predicts the arrival of more inputs,
like when a new user or client starts hitting the Function.

```python
import modal

app = modal.App(image=modal.Image.debian_slim().pip_install("fastapi"))

@app.function(min_containers=3, buffer_containers=3)
def my_warm_greeting():
    return "Hello, world!"
```

## Reduce latency from initialization

Some work is done the first time that a function is invoked
but can be used on every subsequent invocation.
This is
[_amortized work_](https://www.cs.cornell.edu/courses/cs312/2006sp/lectures/lec18.html)
done at initialization.

For example, you may be using a large pre-trained model
whose weights need to be loaded from disk to memory the first time it is used.

This results in longer latencies for the first invocation of a warm container,
which shows up in the application as occasional slow calls: high tail latency or elevated p9Xs.

### Move initialization work out of the first invocation

Some work done on the first invocation can be moved up and completed ahead of time.

Any work that can be saved to disk, like
[downloading model weights](/docs/guide/model-weights),
should be done as early as possible. The results can be included in the
[container's Image](/docs/guide/images)
or saved to a
[Modal Volume](/docs/guide/volumes).

Some work is tricky to serialize, like spinning up a network connection or an inference server.
If you can move this initialization logic out of the function body and into the global scope or a
[container `enter` method](https://modal.com/docs/guide/lifecycle-functions#enter),
you can move this work into the warm up period.
Containers will not be considered warm until all `enter` methods have completed,
so no inputs will be routed to containers that have yet to complete this initialization.

For more on how to use `enter` with machine learning model weights, see
[this guide](/docs/guide/model-weights).

Note that `enter` doesn't get rid of the latency --
it just moves the latency to the warm up period,
where it can be handled by
[running more warm containers](#run-more-warm-containers).

### Share initialization work across cold starts with memory snapshots

Cold starts can also be made faster by using memory snapshots.

Invocations of a Function after the first
are faster in part because the memory is already populated
with values that otherwise need to be computed or read from disk,
like the contents of imported libraries.

Memory snapshotting captures the state of a container's memory
at user-controlled points after it has been warmed up
and reuses that state in future boots, which can substantially
reduce cold start latency penalties and warm up period duration.

Refer to the [memory snapshot](/docs/guide/memory-snapshot)
guide for details.

### Optimize initialization code

Sometimes, there is nothing to be done but to speed this work up.

Here, we share specific patterns that show up in optimizing initialization
in Modal Functions.

#### Load multiple large files concurrently

Often Modal applications need to read large files into memory (eg. model
weights) before they can process inputs. Where feasible these large file
reads should happen concurrently and not sequentially. Concurrent IO takes
full advantage of our platform's high disk and network bandwidth
to reduce latency.

One common example of slow sequential IO is loading multiple independent
Huggingface `transformers` models in series.

```python notest
from transformers import CLIPProcessor, CLIPModel, BlipProcessor, BlipForConditionalGeneration
model_a = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
processor_a = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
model_b = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-large")
processor_b = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-large")
```

The above snippet does four `.from_pretrained` loads sequentially.
None of the components depend on another being already loaded in memory, so they
can be loaded concurrently instead.

They could instead be loaded concurrently using a function like this:

```python notest
from concurrent.futures import ThreadPoolExecutor, as_completed
from transformers import CLIPProcessor, CLIPModel, BlipProcessor, BlipForConditionalGeneration

def load_models_concurrently(load_functions_map: dict) -> dict:
    model_id_to_model = {}
    with ThreadPoolExecutor(max_workers=len(load_functions_map)) as executor:
        future_to_model_id = {
            executor.submit(load_fn): model_id
            for model_id, load_fn in load_functions_map.items()
        }
        for future in as_completed(future_to_model_id.keys()):
            model_id_to_model[future_to_model_id[future]] = future.result()
    return model_id_to_model

components = load_models_concurrently({
    "clip_model": lambda: CLIPModel.from_pretrained("openai/clip-vit-base-patch32"),
    "clip_processor": lambda: CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32"),
    "blip_model": lambda: BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-large"),
    "blip_processor": lambda: BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-large")
})
```

If performing concurrent IO on large file reads does _not_ speed up your cold
starts, it's possible that some part of your function's code is holding the
Python [GIL](https://wiki.python.org/moin/GlobalInterpreterLock) and reducing
the efficacy of the multi-threaded executor.
