# GPU acceleration

Modal makes it easy to run your code on [GPUs](/gpu-glossary/readme).

## Quickstart

Here's a simple example of a Function running on an A100 in Modal:

```python
import modal

image = modal.Image.debian_slim().pip_install("torch")
app = modal.App(image=image)


@app.function(gpu="A100")
def run():
    import torch

    assert torch.cuda.is_available()
```

## Specifying GPU type

You can pick a specific GPU type for your Function via the `gpu` argument.
Modal supports the following values for this parameter:

- `T4`
- `L4`
- `A10`
- `A100`
- `A100-40GB`
- `A100-80GB`
- `L40S`
- `H100`/`H100!`
- `H200`
- `B200`

For instance, to use a B200, you can use `@app.function(gpu="B200")`.

Refer to our [pricing page](/pricing) for the latest pricing on each GPU type.

## Specifying GPU count

You can specify more than 1 GPU per container by appending `:n` to the GPU
argument. For instance, to run a Function with eight H100s:

```python

@app.function(gpu="H100:8")
def run_llama_405b_fp8():
    ...
```

Currently B200, H200, H100, A100, L4, T4 and L40S instances support up to 8 GPUs (up to 1,536 GB GPU RAM),
and A10 instances support up to 4 GPUs (up to 96 GB GPU RAM). Note that requesting
more than 2 GPUs per container will usually result in larger wait times. These
GPUs are always attached to the same physical machine.

## Picking a GPU

For running, rather than training, neural networks, we recommend starting off
with the [L40S](https://resources.nvidia.com/en-us-l40s/l40s-datasheet-28413),
which offers an excellent trade-off of cost and performance and 48 GB of GPU
RAM for storing model weights and activations.

For more on how to pick a GPU for use with neural networks like LLaMA or Stable
Diffusion, and for tips on how to make that GPU go brrr, check out
[Tim Dettemers' blog post](https://timdettmers.com/2023/01/30/which-gpu-for-deep-learning/)
or the
[Full Stack Deep Learning page on Cloud GPUs](https://fullstackdeeplearning.com/cloud-gpus/).

## B200 GPUs

Modal's most powerful GPUs are the [B200s](https://www.nvidia.com/en-us/data-center/dgx-b200/),
NVIDIA's flagship data center chip for the Blackwell [architecture](/gpu-glossary/device-hardware/streaming-multiprocessor-architecture).

To request a B200, set the `gpu` argument to `"B200"`

```python
@app.function(gpu="B200:8")
def run_deepseek():
    ...
```

Check out [this example](/docs/examples/llm_inference) to see how you can use B200s to max out vLLM serving performance for LLaMA 3.1-8B.

Before you jump for the most powerful (and so most expensive) GPU, make sure you
understand where the bottlenecks are in your computations. For example, running
language models with small batch sizes (e.g. one prompt at a time) results in a
[bottleneck on memory, not arithmetic](https://kipp.ly/transformer-inference-arithmetic/).
Since arithmetic throughput has risen faster than memory throughput in recent
hardware generations, speedups for memory-bound GPU jobs are not as extreme and
may not be worth the extra cost.

## H200 and H100 GPUs

[H200s](https://www.nvidia.com/en-us/data-center/h200/) and [H100s](https://www.nvidia.com/en-us/data-center/h100/) are the previous
generation of top-of-the-line data center chips from NVIDIA, based on the Hopper [architecture](/gpu-glossary/device-hardware/streaming-multiprocessor-architecture).
These GPUs have better software support than do Blackwell GPUs (e.g. popular libraries include pre-compiled kernels for Hopper, but not Blackwell),
and they often get the job done at a competitive cost, so they are a common choice of accelerator, on and off Modal.

All H100 GPUs on the Modal platform are of the SXM variant, as can be verified by examining the
[power draw](/docs/guide/gpu-metrics) in the dashboard or with `nvidia-smi`.

### Automatic upgrades to H200s

Modal may automatically upgrade a `gpu="H100"` request to run on an H200.
This automatic upgrade does _not_ change the cost of the GPU.

Kernels [compatible](/gpu-glossary/device-software/compute-capability) with H200s are also compatible with H100s,
so your code will still run, just faster, so long as it doesn't make strict assumptions about memory capacity.
An H200’s [HBM3e memory](/gpu-glossary/device-hardware/gpu-ram)
has a capacity of 141 GB and a bandwidth of 4.8TB/s, 1.75x larger and 1.4x faster than an NVIDIA H100 with HBM3.

In cases where an automatic upgrade to H200 would not be helpful (for instance, benchmarking) you can pass
`gpu=H100!` to avoid it.

## A100 GPUs

[A100s](https://www.nvidia.com/en-us/data-center/a100/) are based on NVIDIA's Ampere [architecture](/gpu-glossary/device-hardware/streaming-multiprocessor-architecture).
Modal offers two versions of the A100: one with 40 GB of RAM and another with 80 GB of RAM.

To request an A100 with 40 GB of [GPU memory](/gpu-glossary/device-hardware/gpu-ram), use `gpu="A100"`:

```python
@app.function(gpu="A100")
def qwen_7b():
    ...
```

Modal may automatically upgrade a `gpu="A100"` request to run on an 80 GB A100.
This automatic upgrade does _not_ change the cost of the GPU.

You can specifically request a 40GB A100 with the string `A100-40GB`.
To specifically request an 80 GB A100, use the string `A100-80GB`:

```python
@app.function(gpu="A100-80GB")
def llama_70b_fp8():
    ...
```

## GPU fallbacks

Modal allows specifying a list of possible GPU types, suitable for Functions that are
compatible with multiple options. Modal respects the ordering of this list and
will try to allocate the most preferred GPU type before falling back to less
preferred ones.

```python
@app.function(gpu=["H100", "A100-40GB:2"])
def run_on_80gb():
    ...
```

See [this example](/docs/examples/gpu_fallbacks) for more detail.

## Multi GPU training

Modal currently supports multi-GPU training on a single node, with multi-node training in closed beta ([contact us](https://modal.com/slack) for access).
Depending on which framework you are using, you may need to use different techniques to train on multiple GPUs.

If the framework re-executes the entrypoint of the Python process (like [PyTorch Lightning](https://lightning.ai/docs/pytorch/stable/index.html)) you need to either set the strategy to `ddp_spawn` or `ddp_notebook` if you wish to invoke the training directly. Another option is to run the training script as a subprocess instead.

```python
@app.function(gpu="A100:2")
def run():
    import subprocess
    import sys
    subprocess.run(
        ["python", "train.py"],
        stdout=sys.stdout, stderr=sys.stderr,
        check=True,
    )
```

## Examples and more resources

For more information about GPUs in general, check out our [GPU Glossary](/gpu-glossary/readme).

Or take a look some examples of Modal apps using GPUs:

- [Fine-tune a character LoRA for your pet](/docs/examples/diffusers_lora_finetune)
- [Fast LLM inference on big GPUs](/docs/examples/llm_inference)
- [Stable Diffusion with a CLI, API, and web UI](/docs/examples/text_to_image)
- [Rendering Blender videos](/docs/examples/blender_video)

<YoutubeEmbed videoId="MLvC7W_b6SA"/>
