# Introduction

Modal is an AI infrastructure platform that lets you:

- Run low latency [inference](/docs/examples/llm_inference) with sub-second cold starts, using open weights or custom models
- Scale out [batch jobs](/docs/guide/batch-processing) to run massively in parallel
- [Train](/docs/examples/hp_sweep_gpt) or [fine-tune](/docs/examples/diffusers_lora_finetune) open weights or custom models on the latest GPUs
- Spin up thousands of isolated and secure [Sandboxes](/docs/guide/sandbox) to execute AI generated code
- Launch GPU-backed [Notebooks](/docs/guide/notebooks-modal) in seconds and collaborate with your colleagues in real-time

You get [full serverless execution and pricing](/pricing) because we host everything and charge per second of usage.

Notably, there’s zero configuration in Modal - everything, including [container environments](/docs/guide/images) and [GPU specification](/docs/guide/gpu), is code. Take a breath of fresh air and feel how good it tastes with no YAML in it.

Here's a complete, minimal example of LLM inference running on Modal:

```python
from pathlib import Path

import modal

app = modal.App("example-inference")
image = modal.Image.debian_slim().uv_pip_install("transformers[torch]")


@app.function(gpu="h100", image=image)
def chat(prompt: str | None = None) -> list[dict]:
    from transformers import pipeline

    if prompt is None:
        prompt = f"/no_think Read this code.\n\n{Path(__file__).read_text()}\nIn one paragraph, what does the code do?"

    print(prompt)
    context = [{"role": "user", "content": prompt}]

    chatbot = pipeline(
        model="Qwen/Qwen3-1.7B-FP8", device_map="cuda", max_new_tokens=1024
    )
    result = chatbot(context)
    print(result[0]["generated_text"][-1]["content"])

    return result
```

That's it! You can copy and paste that text into a Python file in your favorite editor and then run it with `modal run path/to/file.py`.

## How does it work?

Modal takes your code, puts it in a container, and executes it in the cloud. If you get a lot of traffic, Modal automatically scales up the number of containers as needed. This means you don't need to mess with Kubernetes, Docker, or even an AWS account.

We pool capacity over all major clouds. That means we can optimize for both high GPU availability and low cost by dynamically deciding where to run your code based on the best available capacity.

## Programming language support

Python is the primary language for building Modal applications and implementing Modal Functions, but you can also use [JavaScript/TypeScript or Go](/docs/guide/sdk-javascript-go) to call Modal Functions, run Sandboxes, and manage Modal resources.

## Getting started

Developing with Modal is easy because you don't have to set up any infrastructure. Just:

1. Create an account at [modal.com](https://modal.com)
2. Run `pip install modal` to install the `modal` Python package
3. Run `modal setup` to authenticate (if this doesn't work, try `python -m modal setup`)

…and you can start running jobs right away. Check out some of our simple getting started examples:

- [Hello, world!](/docs/examples/hello_world)
- [A simple web scraper](/docs/examples/webscraper)

And when you're ready for something fancier, explore our [full library of examples](/docs/examples), like:

- [Running your own LLM inference](/docs/examples/llm_inference)
- [Transcribing speech in real time with Kyutai STT](/docs/examples/streaming_kyutai_stt)
- [Fine-tuning Flux](/docs/examples/diffusers_lora_finetune)
- [Building a coding agent with Modal Sandboxes and LangGraph](/docs/examples/agent)
- [Training a small language model from scratch](/docs/examples/hp_sweep_gpt)
- [Parallel processing of Parquet files on S3](/docs/examples/s3_bucket_mount)
- [Parsing documents with dots.ocr in a Modal Notebook](https://modal.com/notebooks/modal-labs/_/nb-8wvXoGoAcba8sRF8VkVg18)

You can also learn Modal interactively without installing anything through our [code playground](/playground).
