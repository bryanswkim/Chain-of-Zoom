# Job processing

Modal can be used as a scalable job queue to handle asynchronous tasks submitted
from a web app or any other Python application. This allows you to offload up to 1 million
long-running or resource-intensive tasks to Modal, while your main application
remains responsive.

## Creating jobs with .spawn()

The basic pattern for using Modal as a job queue involves three key steps:

1. Defining and deploying the job processing function using `modal deploy`.
2. Submitting a job using
   [`modal.Function.spawn()`](/docs/reference/modal.Function#spawn)
3. Polling for the job's result using
   [`modal.FunctionCall.get()`](/docs/reference/modal.FunctionCall#get)

Here's a simple example that you can run with `modal run my_job_queue.py`:

```python
# my_job_queue.py
import modal

app = modal.App("my-job-queue")

@app.function()
def process_job(data):
    # Perform the job processing here
    return {"result": data}

def submit_job(data):
    # Since the `process_job` function is deployed, need to first look it up
    process_job = modal.Function.from_name("my-job-queue", "process_job")
    call = process_job.spawn(data)
    return call.object_id

def get_job_result(call_id):
    function_call = modal.FunctionCall.from_id(call_id)
    try:
        result = function_call.get(timeout=5)
    except modal.exception.OutputExpiredError:
        result = {"result": "expired"}
    except TimeoutError:
        result = {"result": "pending"}
    return result

@app.local_entrypoint()
def main():
    data = "my-data"

    # Submit the job to Modal
    call_id = submit_job(data)
    print(get_job_result(call_id))
```

In this example:

- `process_job` is the Modal function that performs the actual job processing.
  To deploy the `process_job` function on Modal, run
  `modal deploy my_job_queue.py`.
- `submit_job` submits a new job by first looking up the deployed `process_job`
  function, then calling `.spawn()` with the job data. It returns the unique ID
  of the spawned function call.
- `get_job_result` attempts to retrieve the result of a previously submitted job
  using [`FunctionCall.from_id()`](/docs/reference/modal.FunctionCall#from_id) and
  [`FunctionCall.get()`](/docs/reference/modal.FunctionCall#get).
  [`FunctionCall.get()`](/docs/reference/modal.FunctionCall#get) waits indefinitely
  by default. It takes an optional timeout argument that specifies the maximum
  number of seconds to wait, which can be set to 0 to poll for an output
  immediately. Here, if the job hasn't completed yet, we return a pending
  response.
- The results of a `.spawn()` are accessible via `FunctionCall.get()` for up to
  7 days after completion. After this period, we return an expired response.

[Document OCR Web App](/docs/examples/doc_ocr_webapp) is an example that uses
this pattern.

## Integration with web frameworks

You can easily integrate the job queue pattern with web frameworks like FastAPI.
Here's an example, assuming that you have already deployed `process_job` on
Modal with `modal deploy` as above. This example won't work if you haven't
deployed your app yet.

```python
# my_job_queue_endpoint.py
import modal

image = modal.Image.debian_slim().pip_install("fastapi[standard]")
app = modal.App("fastapi-modal", image=image)


@app.function()
@modal.asgi_app()
@modal.concurrent(max_inputs=20)
def fastapi_app():
    from fastapi import FastAPI

    web_app = FastAPI()

    @web_app.post("/submit")
    async def submit_job_endpoint(data):
        process_job = modal.Function.from_name("my-job-queue", "process_job")

        call = await process_job.spawn.aio(data)
        return {"call_id": call.object_id}


    @web_app.get("/result/{call_id}")
    async def get_job_result_endpoint(call_id: str):
        function_call = modal.FunctionCall.from_id(call_id)
        try:
            result = await function_call.get.aio(timeout=0)
        except modal.exception.OutputExpiredError:
            return fastapi.responses.JSONResponse(content="", status_code=404)
        except TimeoutError:
            return fastapi.responses.JSONResponse(content="", status_code=202)

        return result

    return web_app
```

In this example:

- The `/submit` endpoint accepts job data, submits a new job using
  `await process_job.spawn.aio()`, and returns the job's ID to the client.
- The `/result/{call_id}` endpoint allows the client to poll for the job's
  result using the job ID. If the job hasn't completed yet, it returns a 202
  status code to indicate that the job is still being processed. If the job
  has expired, it returns a 404 status code to indicate that the job is not found.

You can try this app by serving it with `modal serve`:

```shell
modal serve my_job_queue_endpoint.py
```

Then interact with its endpoints with `curl`:

```shell
# Make a POST request to your app endpoint with.
$ curl -X POST $YOUR_APP_ENDPOINT/submit?data=data
{"call_id":"fc-XXX"}

# Use the call_id value from above.
$ curl -X GET $YOUR_APP_ENDPOINT/result/fc-XXX
```

## Scaling and reliability

Modal automatically scales the job queue based on the workload, spinning up new
instances as needed to process jobs concurrently. It also provides built-in
reliability features like automatic retries and timeout handling.

You can customize the behavior of the job queue by configuring the
`@app.function()` decorator with options like
[`retries`](/docs/guide/retries#function-retries),
[`timeout`](/docs/guide/timeouts#timeouts), and
[`max_containers`](/docs/guide/scale#configuring-autoscaling-behavior).
