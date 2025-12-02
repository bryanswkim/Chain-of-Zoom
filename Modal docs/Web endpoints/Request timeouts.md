# Request timeouts

Web endpoint (a.k.a. webhook) requests should complete quickly, ideally within a
few seconds. All web endpoint function types
([`web_endpoint`, `asgi_app`, `wsgi_app`](/docs/reference/modal.web_endpoint))
have a maximum HTTP request timeout of 150 seconds enforced. However, the
underlying Modal function can have a longer [timeout](/docs/guide/timeouts).

In case the function takes more than 150 seconds to complete, a HTTP status 303
redirect response is returned pointing at the original URL with a special query
parameter linking it that request. This is the _result URL_ for your function.
Most web browsers allow for up to 20 such redirects, effectively allowing up to
50 minutes (20 \* 150 s) for web endpoints before the request times out.

(**Note:** This does not work with requests that require
[CORS](https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS), since the
response will not have been returned from your code in time for the server to
populate CORS headers.)

Some libraries and tools might require you to add a flag or option in order to
follow redirects automatically, e.g. `curl -L ...` or `http --follow ...`.

The _result URL_ can be reloaded without triggering a new request. It will block
until the request completes.

(**Note:** As of March 2025, the Python standard library's `urllib` module has the
maximum number of redirects to any single URL set to 4 by default ([source](https://github.com/python/cpython/blob/main/Lib/urllib/request.py)), which would limit the total timeout to 12.5 minutes (5 \* 150 s = 750 s) unless this setting is overridden.)

## Polling solutions

Sometimes it can be useful to be able to poll for results rather than wait for a
long running HTTP request. The easiest way to do this is to have your web
endpoint spawn a `modal.Function` call and return the function call id that
another endpoint can use to poll the submitted function's status. Here is an
example:

```python
import fastapi

import modal


image = modal.Image.debian_slim().pip_install("fastapi[standard]")
app = modal.App(image=image)

web_app = fastapi.FastAPI()


@app.function()
@modal.asgi_app()
def fastapi_app():
    return web_app


@app.function()
def slow_operation():
    ...


@web_app.post("/accept")
async def accept_job(request: fastapi.Request):
    call = slow_operation.spawn()
    return {"call_id": call.object_id}


@web_app.get("/result/{call_id}")
async def poll_results(call_id: str):
    function_call = modal.FunctionCall.from_id(call_id)
    try:
        return function_call.get(timeout=0)
    except TimeoutError:
        http_accepted_code = 202
        return fastapi.responses.JSONResponse({}, status_code=http_accepted_code)
```

[_Document OCR Web App_](/docs/examples/doc_ocr_webapp) is an example that uses
this pattern.
