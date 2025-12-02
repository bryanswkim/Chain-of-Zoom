# Batch Processing

Modal is optimized for large-scale batch processing, allowing functions to scale to thousands of parallel containers with zero additional configuration. Function calls can be submitted asynchronously for background execution, eliminating the need to wait for jobs to finish or tune resource allocation.

This guide covers Modal's batch processing capabilities, from basic invocation to integration with existing pipelines.

## Background Execution with `.spawn_map`

The fastest way to submit multiple jobs for asynchronous processing is by invoking a function with `.spawn_map`. When combined with the [`--detach`](/docs/reference/cli/run) flag, your App continues running until all jobs are completed.

Here's an example of submitting 100,000 videos for parallel embedding. You can disconnect after submission, and the processing will continue to completion in the background:

```python
# Kick off asynchronous jobs with `modal run --detach batch_processing.py`
import modal

app = modal.App("batch-processing-example")
volume = modal.Volume.from_name("video-embeddings", create_if_missing=True)

@app.function(volumes={"/data": volume})
def embed_video(video_id: int):
    # Business logic:
    # - Load the video from the volume
    # - Embed the video
    # - Save the embedding to the volume
    ...

@app.local_entrypoint()
def main():
    embed_video.spawn_map(range(100_000))
```

This pattern works best for jobs that store results externally—for example, in a [Modal Volume](/docs/guide/volumes), [Cloud Bucket Mount](/docs/guide/cloud-bucket-mounts), or your own database\*.

_\* For database connections, consider using [Modal Proxy](/docs/guide/proxy-ips) to maintain a static IP across thousands of containers._

## Parallel Processing with `.map`

Using `.map` allows you to offload expensive computations to powerful machines while gathering results. This is particularly useful for pipeline steps with bursty resource demands. Modal handles all infrastructure provisioning and de-provisioning automatically.

Here's how to implement parallel video similarity queries as a single Modal function call:

```python
# Run jobs and collect results with `modal run gather.py`
import modal

app = modal.App("gather-results-example")

@app.function(gpu="L40S")
def compute_video_similarity(query: str, video_id: int) -> tuple[int, int]:
    # Embed video with GPU acceleration & compute similarity with query
    return video_id, score


@app.local_entrypoint()
def main():
    import itertools

    queries = itertools.repeat("Modal for batch processing")
    video_ids = range(100_000)

    for video_id, score in compute_video_similarity.map(queries, video_ids):
        # Process results (e.g., extract top 5 most similar videos)
        pass
```

This example runs `compute_video_similarity` on an autoscaling pool of L40S GPUs, returning scores to a local process for further processing.

## Integration with Existing Systems

The recommended way to use Modal Functions within your existing data pipeline is through [deployed function invocation](/docs/guide/trigger-deployed-functions). After deployment, you can call Modal functions from external systems:

```python
def external_function(inputs):
    compute_similarity = modal.Function.from_name(
        "gather-results-example",
        "compute_video_similarity"
    )
    for result in compute_similarity.map(inputs):
        # Process results
        pass
```

You can invoke Modal Functions from any Python context, gaining access to built-in observability, resource management, and GPU acceleration.
