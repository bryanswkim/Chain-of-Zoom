# Using CUDA on Modal

Modal makes it easy to accelerate your workloads with datacenter-grade NVIDIA GPUs.

To take advantage of the hardware, you need to use matching software: the CUDA stack.
This guide explains the components of that stack and how to install them on Modal.
For more on which GPUs are available on Modal and how to choose a GPU for your use case,
see [this guide](/docs/guide/gpu). For a deep dive on both the
[GPU hardware](/gpu-glossary/device-hardware) and [software](/gpu-glossary/device-software)
and for even more detail on [the CUDA stack](/gpu-glossary/host-software/),
see our [GPU Glossary](/gpu-glossary/readme).

Here's the tl;dr:

- The [NVIDIA Accelerated Graphics Driver for Linux-x86_64](https://docs.nvidia.com/cuda/cuda-installation-guide-linux/#driver-installation), version 575.57.08,
  and [CUDA Driver API](https://docs.nvidia.com/cuda/archive/12.9.0/cuda-driver-api/index.html), version 12.9, are already installed.
  You can call `nvidia-smi` or run compiled CUDA programs from any Modal Function with access to a GPU.
- That means you can install many popular libraries like `torch` that bundle their other CUDA dependencies [with a simple `pip_install`](#install-gpu-accelerated-torch-and-transformers-with-pip_install).
- For bleeding-edge libraries like `flash-attn`, you may need to install CUDA dependencies manually.
  To make your life easier, [use an existing image](#for-more-complex-setups-use-an-officially-supported-cuda-image).

## What is CUDA?

When someone refers to "installing CUDA" or "using CUDA",
they are referring not to a library, but to a
[stack](/gpu-glossary/host-software/cuda-software-platform) with multiple layers.
Your application code (and its dependencies) can interact
with the stack at different levels.

![The CUDA stack](../../assets/docs/cuda-stack-diagram.png)

This leads to a lot of confusion. To help clear that up, the following sections explain each component in detail.

### Level 0: Kernel-mode driver components

At the lowest level are the [_kernel-mode driver components_](https://docs.nvidia.com/cuda/cuda-installation-guide-linux/#nvidia-open-gpu-kernel-modules).
The Linux kernel is essentially a single program operating the entire machine and all of its hardware.
To add hardware to the machine, this program is extended by loading new modules into it.
These components communicate directly with hardware -- in this case the GPU.

Because they are kernel modules, these driver components are tightly integrated with the host operating system
that runs your containerized Modal Functions and are not something you can inspect or change yourself.

### Level 1: User-mode driver API

All action in Linux that doesn't occur in the kernel occurs in [user space](https://en.wikipedia.org/wiki/User_space).
To talk to the kernel drivers from our user space programs, we need _user-mode driver components_.

Most prominently, that includes:

- the [CUDA Driver API](/gpu-glossary/host-software/cuda-driver-api),
  a [shared object](https://en.wikipedia.org/wiki/Shared_library) called `libcuda.so`.
  This object exposes functions like [`cuMemAlloc`](https://docs.nvidia.com/cuda/archive/12.8.0/cuda-driver-api/group__CUDA__MEM.html#group__CUDA__MEM_1gb82d2a09844a58dd9e744dc31e8aa467),
  for allocating GPU memory.
- the [NVIDIA management library](https://developer.nvidia.com/management-library-nvml), `libnvidia-ml.so`, and its command line interface [`nvidia-smi`](https://developer.nvidia.com/system-management-interface).
  You can use these tools to check the status of the system's GPU(s).

These components are installed on all Modal machines with access to GPUs.
Because they are user-level components, you can use them directly:

```python runner:ModalRunner
import modal

app = modal.App()

@app.function(gpu="any")
def check_nvidia_smi():
    import subprocess
    output = subprocess.check_output(["nvidia-smi"], text=True)
    assert "Driver Version:" in output
    assert "CUDA Version:" in output
    print(output)
    return output
```

### Level 2: CUDA Toolkit

Wrapping the CUDA Driver API is the [CUDA Runtime API](/gpu-glossary/host-software/cuda-runtime-api), the `libcudart.so` shared library.
This API includes functions like [`cudaLaunchKernel`](https://docs.nvidia.com/cuda/archive/12.8.0/cuda-runtime-api/group__CUDART__HIGHLEVEL.html#group__CUDART__HIGHLEVEL_1g7656391f2e52f569214adbfc19689eb3)
and is more commonly used in CUDA programs (see [this HackerNews comment](https://news.ycombinator.com/item?id=20616385) for color commentary on why).
This shared library is _not_ installed by default on Modal.

The CUDA Runtime API is generally installed as part of the larger [NVIDIA CUDA Toolkit](https://docs.nvidia.com/cuda/index.html),
which includes the [NVIDIA CUDA compiler driver](/gpu-glossary/host-software/nvcc) (`nvcc`) and its toolchain
and a number of [useful goodies](/gpu-glossary/host-software/cuda-binary-utilities) for writing and debugging CUDA programs (`cuobjdump`, `cudnn`, profilers, etc.).

Contemporary GPU-accelerated machine learning workloads like LLM inference frequently make use of many components of the CUDA Toolkit,
such as the run-time compilation library [`nvrtc`](https://docs.nvidia.com/cuda/archive/12.8.0/nvrtc/index.html).

So why aren't these components installed along with the drivers?
A compiled CUDA program can run without the CUDA Runtime API installed on the system,
by [statically linking](https://en.wikipedia.org/wiki/Static_library) the CUDA Runtime API into the program binary,
though this is fairly uncommon for CUDA-accelerated Python programs.
Additionally, older versions of these components are needed for some applications
and some application deployments even use several versions at once.
Both patterns are compatible with the host machine driver provided on Modal.

## Install GPU-accelerated `torch` and `transformers` with `pip_install`

The components of the CUDA Toolkit can be installed via `pip`,
via PyPI packages like [`nvidia-cuda-runtime-cu12`](https://pypi.org/project/nvidia-cuda-runtime-cu12/)
and [`nvidia-cuda-nvrtc-cu12`](https://pypi.org/project/nvidia-cuda-nvrtc-cu12/).
These components are listed as dependencies of some popular GPU-accelerated Python libraries, like `torch`.

Because Modal already includes the lower parts of the CUDA stack, you can install these libraries
with [the `pip_install` method of `modal.Image`](/docs/guide/images#add-python-packages-with-pip_install), just like any other Python library:

```python
image = modal.Image.debian_slim().pip_install("torch")


@app.function(gpu="any", image=image)
def run_torch():
    import torch
    has_cuda = torch.cuda.is_available()
    print(f"It is {has_cuda} that torch can access CUDA")
    return has_cuda
```

Many libraries for running open-weights models, like `transformers` and `vllm`,
use `torch` under the hood and so can be installed in the same way:

```python
image = modal.Image.debian_slim().pip_install("transformers[torch]")
image = image.apt_install("ffmpeg")  # for audio processing


@app.function(gpu="any", image=image)
def run_transformers():
    from transformers import pipeline
    transcriber = pipeline(model="openai/whisper-tiny.en", device="cuda")
    result = transcriber("https://modal-cdn.com/mlk.flac")
    print(result["text"])  # I have a dream that one day this nation will rise up live out the true meaning of its creed
```

## For more complex setups, use an officially-supported CUDA image

The disadvantage of installing the CUDA stack via `pip` is that
many other libraries that depend on its components being installed as normal system packages cannot find them.

For these cases, we recommend you use an image that already has the full CUDA stack installed as system packages
and all environment variables set correctly, like the [`nvidia/cuda:*-devel-*` images on Docker Hub](https://hub.docker.com/r/nvidia/cuda).

[TensorRT-LLM](https://nvidia.github.io/TensorRT-LLM/overview.html) is an inference engine that accelerates and optimizes performance for the large language models. It requires the full CUDA toolkit for installation.

```python
cuda_version = "12.8.1"  # should be no greater than host CUDA version
flavor = "devel"  # includes full CUDA toolkit
operating_sys = "ubuntu24.04"
tag = f"{cuda_version}-{flavor}-{operating_sys}"
HF_CACHE_PATH = "/cache"


image = (
    modal.Image.from_registry(f"nvidia/cuda:{tag}", add_python="3.12")
    .entrypoint([])  # remove verbose logging by base image on entry
    .apt_install("libopenmpi-dev")  # required for tensorrt
    .pip_install("tensorrt-llm==0.19.0", "pynvml", extra_index_url="https://pypi.nvidia.com")
    .pip_install("hf-transfer", "huggingface_hub[hf_xet]")
    .env({"HF_HUB_CACHE": HF_CACHE_PATH, "HF_HUB_ENABLE_HF_TRANSFER": "1", "PMIX_MCA_gds": "hash"})
)


app = modal.App("tensorrt-llm", image=image)
hf_cache_volume = modal.Volume.from_name("hf_cache_tensorrt", create_if_missing=True)


@app.function(gpu="A10G", volumes={HF_CACHE_PATH: hf_cache_volume})
def run_tiny_model():
    from tensorrt_llm import LLM, SamplingParams

    sampling_params = SamplingParams(temperature=0.8, top_p=0.95)

    llm = LLM(model="TinyLlama/TinyLlama-1.1B-Chat-v1.0")

    output = llm.generate("The capital of France is", sampling_params)
    print(f"Generated text: {output.outputs[0].text}")
    return output.outputs[0].text
```

Make sure to choose a version of CUDA that is no greater than the version provided by the host machine.
Older minor (`12.*`) versions are guaranteed to be compatible with the host machine's driver,
but older major (`11.*`, `10.*`, etc.) versions may not be.

## What next?

For more on accessing and choosing GPUs on Modal, check out [this guide](/docs/guide/gpu).
To dive deep on GPU internals, check out our [GPU Glossary](/gpu-glossary/readme).

To see these installation patterns in action, check out these examples:

- [Fast LLM inference on big GPUs](/docs/examples/llm_inference)
- [Finetune a character LoRA for your pet](/docs/examples/diffusers_lora_finetune)
- [Optimized Flux inference](/docs/examples/flux)
