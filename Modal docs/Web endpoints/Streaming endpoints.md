# Streaming endpoints

Modal web endpoints support streaming responses using FastAPI's
[`StreamingResponse`](https://fastapi.tiangolo.com/advanced/custom-response/#streamingresponse)
class. This class accepts asynchronous generators, synchronous generators, or
any Python object that implements the
[_iterator protocol_](https://docs.python.org/3/library/stdtypes.html#typeiter),
and can be used with Modal Functions!

## Simple example

This simple example combines Modal's `@modal.fastapi_endpoint` decorator with a
`StreamingResponse` object to produce a real-time SSE response.

```python
import time

def fake_event_streamer():
    for i in range(10):
        yield f"data: some data {i}\n\n".encode()
        time.sleep(0.5)


@app.function(image=modal.Image.debian_slim().pip_install("fastapi[standard]"))
@modal.fastapi_endpoint()
def stream_me():
    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        fake_event_streamer(), media_type="text/event-stream"
    )
```

If you serve this web endpoint and hit it with `curl`, you will see the ten SSE
events progressively appear in your terminal over a ~5 second period.

```shell
curl --no-buffer https://modal-labs--example-streaming-stream-me.modal.run
```

The MIME type of `text/event-stream` is important in this example, as it tells
the downstream web server to return responses immediately, rather than buffering
them in byte chunks (which is more efficient for compression).

You can still return other content types like large files in streams, but they
are not guaranteed to arrive as real-time events.

## Streaming responses with `.remote`

A Modal Function wrapping a generator function body can have its response passed
directly into a `StreamingResponse`. This is particularly useful if you want to
do some GPU processing in one Modal Function that is called by a CPU-based web
endpoint Modal Function.

```python
@app.function(gpu="any")
def fake_video_render():
    for i in range(10):
        yield f"data: finished processing some data from GPU {i}\n\n".encode()
        time.sleep(1)


@app.function(image=modal.Image.debian_slim().pip_install("fastapi[standard]"))
@modal.fastapi_endpoint()
def hook():
    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        fake_video_render.remote_gen(), media_type="text/event-stream"
    )
```

## Streaming responses with `.map` and `.starmap`

You can also combine Modal Function parallelization with streaming responses,
enabling applications to service a request by farming out to dozens of
containers and iteratively returning result chunks to the client.

```python
@app.function()
def map_me(i):
    return f"segment {i}\n"


@app.function(image=modal.Image.debian_slim().pip_install("fastapi[standard]"))
@modal.fastapi_endpoint()
def mapped():
    from fastapi.responses import StreamingResponse
    return StreamingResponse(map_me.map(range(10)), media_type="text/plain")
```

This snippet will spread the ten `map_me(i)` executions across containers, and
return each string response part as it completes. By default the results will be
ordered, but if this isn't necessary pass `order_outputs=False` as keyword
argument to the `.map` call.

### Asynchronous streaming

The example above uses a synchronous generator, which automatically runs on its
own thread, but in asynchronous applications, a loop over a `.map` or `.starmap`
call can block the event loop. This will stop the `StreamingResponse` from
returning response parts iteratively to the client.

To avoid this, you can use the `.aio()` method to convert a synchronous `.map`
into its async version. Also, other blocking calls should be offloaded to a
separate thread with `asyncio.to_thread()`. For example:

```python
@app.function(gpu="any", image=modal.Image.debian_slim().pip_install("fastapi[standard]"))
@modal.fastapi_endpoint()
async def transcribe_video(request):
    from fastapi.responses import StreamingResponse

    segments = await asyncio.to_thread(split_video, request)
    return StreamingResponse(wrapper(segments), media_type="text/event-stream")


# Notice that this is an async generator.
async def wrapper(segments):
    async for partial_result in transcribe_video.map.aio(segments):
        yield "data: " + partial_result + "\n\n"
```

## Further examples

- Complete code the for the simple examples given above is available
  [in our modal-examples Github repository](https://github.com/modal-labs/modal-examples/blob/main/07_web_endpoints/streaming.py).
- [An end-to-end example of streaming Youtube video transcriptions with OpenAI's whisper model.](https://github.com/modal-labs/modal-examples/blob/main/06_gpu_and_ml/openai_whisper/streaming/main.py)
