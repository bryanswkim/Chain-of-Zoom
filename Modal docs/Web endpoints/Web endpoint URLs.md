# Web endpoint URLs

This guide documents the behavior of URLs for [web endpoints](/docs/guide/webhooks)
on Modal: automatic generation, configuration, programmatic retrieval, and more.

## Determine the URL of a web endpoint from code

Modal Functions with the
[`fastapi_endpoint`](/docs/reference/modal.fastapi_endpoint),
[`asgi_app`](/docs/reference/modal.asgi_app),
[`wsgi_app`](/docs/reference/modal.wsgi_app),
or [`web_server`](/docs/reference/modal.web_server) decorator
are made available over the Internet when they are
[`serve`d](/docs/reference/cli/serve) or [`deploy`ed](/docs/reference/cli/deploy)
and so they have a URL.

This URL is displayed in the `modal` CLI output
and is available in the Modal [dashboard](/apps) for the Function.

To determine a Function's URL programmatically,
check its [`get_web_url()`](/docs/reference/modal.Function#get_web_url)
property:

```python
@app.function(image=modal.Image.debian_slim().pip_install("fastapi[standard]"))
@modal.fastapi_endpoint(docs=True)
def show_url() -> str:
    return show_url.get_web_url()
```

For deployed Functions, this also works from other Python code!
You just need to do a [`from_name`](/docs/reference/modal.Function#from_name)
based on the name of the Function and its [App](/docs/guide/apps):

```python notest
import requests

remote_function = modal.Function.from_name("app", "show_url")
remote_function.get_web_url() == requests.get(handle.get_web_url()).json()
```

## Auto-generated URLs

By default, Modal Functions
will be served from the `modal.run` domain.
The full URL will be constructed from a number of pieces of information
to uniquely identify the endpoint.

At a high-level, web endpoint URLs for deployed applications have the
following structure: `https://<source>--<label>.modal.run`.

The `source` component represents the workspace and environment where the App is
deployed. If your workspace has only a single environment, the `source` will
just be the workspace name. Multiple environments are disambiguated by an
["environment suffix"](/docs/guide/environments#environment-web-suffixes), so
the full source would be `<workspace>-<suffix>`. However, one environment per
workspace is allowed to have a null suffix, in which case the source would just
be `<workspace>`.

The `label` component represents the specific App and Function that the endpoint
routes to. By default, these are concatenated with a hyphen, so the label would
be `<app>-<function>`.

These components are normalized to contain only lowercase letters, numerals, and dashes.

To put this all together, consider the following example. If a member of the
`ECorp` workspace uses the `main` environment (which has `prod` as its web
suffix) to deploy the `text_to_speech` app with a webhook for the `flask-app`
function, the URL will have the following components:

- _Source_:
  - _Workspace name slug_: `ECorp` → `ecorp`
  - _Environment web suffix slug_: `main` → `prod`
- _Label_:
  - _App name slug_: `text_to_speech` → `text-to-speech`
  - _Function name slug_: `flask_app` → `flask-app`

The full URL will be `https://ecorp-prod--text-to-speech-flask-app.modal.run`.

## User-specified labels

It's also possible to customize the `label` used for each Function
by passing a parameter to the relevant endpoint decorator:

```python
import modal

image = modal.Image.debian_slim().pip_install("fastapi")
app = modal.App(name="text_to_speech", image=image)


@app.function()
@modal.fastapi_endpoint(label="speechify")
def web_endpoint_handler():
    ...
```

Building on the example above, this code would produce the following URL:
`https://ecorp-prod--speechify.modal.run`.

User-specified labels are not automatically normalized, but labels with
invalid characters will be rejected.

## Ephemeral apps

To support development workflows, webhooks for ephemeral apps (i.e., apps
created with `modal serve`) will have a `-dev` suffix appended to their URL
label (regardless of whether the label is auto-generated or user-specified).
This prevents development work from interfering with deployed versions of the
same app.

If an ephemeral app is serving a webhook while another ephemeral webhook is
created seeking the same web endpoint label, the new function will _steal_ the
running webhook's label.

This ensures that the latest iteration of the ephemeral function is
serving requests and that older ones stop receiving web traffic.

## Truncation

If a generated subdomain label is longer than 63 characters, it will be
truncated.

For example, the following subdomain label is too long, 67 characters:
`ecorp--text-to-speech-really-really-realllly-long-function-name-dev`.

The truncation happens by calculating a SHA-256 hash of the overlong label, then
taking the first 6 characters of this hash. The overlong subdomain label is
truncated to 56 characters, and then joined by a dash to the hash prefix. In
the above example, the resulting URL would be
`ecorp--text-to-speech-really-really-rea-1b964b-dev.modal.run`.

The combination of the label hashing and truncation provides a unique list of 63
characters, complying with both DNS system limits and uniqueness requirements.

## Custom domains

**Custom domains are available on our
[Team and Enterprise plans](/settings/plans).**

For more customization, you can use your own domain names with Modal web
endpoints. If your [plan](/pricing) supports custom domains, visit the [Domains
tab](/settings/domains) in your workspace settings to add a domain name to your
workspace.

You can use three kinds of domains with Modal:

- **Apex:** root domain names like `example.com`
- **Subdomain:** single subdomain entries such as `my-app.example.com`,
  `api.example.com`, etc.
- **Wildcard domain:** either in a subdomain like `*.example.com`, or in a
  deeper level like `*.modal.example.com`

You'll be asked to update your domain DNS records with your domain name
registrar and then validate the configuration in Modal. Once the records have
been properly updated and propagated, your custom domain will be ready to use.

You can assign any Modal web endpoint to any registered domain in your workspace
with the `custom_domains` argument.

```python
import modal

app = modal.App("custom-domains-example")


@app.function()
@modal.fastapi_endpoint(custom_domains=["api.example.com"])
def hello(message: str):
    return {"message": f"hello {message}"}
```

You can then run `modal deploy` to put your web endpoint online, live.

```shell
$ curl -s https://api.example.com?message=world
{"message": "hello world"}
```

Note that Modal automatically generates and renews TLS certificates for your
custom domains. Since we do this when your domain is first accessed, there may
be an additional 1-2s latency on the first request. Additional requests use a
cached certificate.

You can also register multiple domain names and associate them with the same web
endpoint.

```python
import modal

app = modal.App("custom-domains-example-2")


@app.function()
@modal.fastapi_endpoint(custom_domains=["api.example.com", "api.example.net"])
def hello(message: str):
    return {"message": f"hello {message}"}
```

For **Wildcard** domains, Modal will automatically resolve arbitrary custom
endpoints (and issue TLS certificates). For example, if you add the wildcard
domain `*.example.com`, then you can create any custom domains under
`example.com`:

```python
import random
import modal

app = modal.App("custom-domains-example-2")

random_domain_name = random.choice(range(10))


@app.function()
@modal.fastapi_endpoint(custom_domains=[f"{random_domain_name}.example.com"])
def hello(message: str):
    return {"message": f"hello {message}"}
```

Custom domains can also be used with
[ASGI](https://modal.com/docs/reference/modal.asgi_app#modalasgi_app) or
[WSGI](https://modal.com/docs/reference/modal.wsgi_app) apps using the same
`custom_domains` argument.
