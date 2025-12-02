# Secrets

Securely provide credentials and other sensitive information to your Modal Functions with Secrets.

You can create and edit Secrets via
the [dashboard](/secrets),
the command line interface ([`modal secret`](/docs/reference/cli/secret)), and
programmatically from Python code ([`modal.Secret`](/docs/reference/modal.Secret)).

To inject Secrets into the container running your Function, add the
`secrets=[...]` argument to your `app.function` or `app.cls` decoration.

## Deploy Secrets from the Modal Dashboard

The most common way to create a Modal Secret is to use the
[Secrets panel of the Modal dashboard](/secrets),
which also shows any existing Secrets.

When you create a new Secret, you'll be prompted with a number of templates to help you get started.
These templates demonstrate standard formats for credentials for everything from Postgres and MongoDB
to Weights & Biases and Hugging Face.

## Use Secrets in your Modal Apps

You can then use your Secret by constructing it `from_name` when defining a Modal App
and then accessing its contents as environment variables.
For example, if you have a Secret called `secret-keys` containing the key
`MY_PASSWORD`:

```python
@app.function(secrets=[modal.Secret.from_name("secret-keys")])
def some_function():
    import os

    secret_key = os.environ["MY_PASSWORD"]
    ...
```

Each Secret can contain multiple keys and values but you can also inject
multiple Secrets, allowing you to separate Secrets into smaller reusable units:

```python
@app.function(secrets=[
    modal.Secret.from_name("my-secret-name"),
    modal.Secret.from_name("other-secret"),
])
def other_function():
    ...
```

The Secrets are applied in order, so key-values from later `modal.Secret`
objects in the list will overwrite earlier key-values in the case of a clash.
For example, if both `modal.Secret` objects above contained the key `FOO`, then
the value from `"other-secret"` would always be present in `os.environ["FOO"]`.

## Create Secrets programmatically

In addition to defining Secrets on the web dashboard, you can
programmatically create a Secret directly in your script and send it along to
your Function using `Secret.from_dict(...)`. This can be useful if you want to
send Secrets from your local development machine to the remote Modal App.

```python
import os

if modal.is_local():
    local_secret = modal.Secret.from_dict({"FOO": os.environ["LOCAL_FOO"]})
else:
    local_secret = modal.Secret.from_dict({})


@app.function(secrets=[local_secret])
def some_function():
    import os

    print(os.environ["FOO"])
```

If you have [`python-dotenv`](https://pypi.org/project/python-dotenv/) installed,
you can also use `Secret.from_dotenv()` to create a Secret from the variables in a `.env`
file

```python
@app.function(secrets=[modal.Secret.from_dotenv()])
def some_other_function():
    print(os.environ["USERNAME"])
```

## Interact with Secrets from the command line

You can create, list, and delete your Modal Secrets with the `modal secret` command line interface.

View your Secrets and their timestamps with

```bash
modal secret list
```

Create a new Secret by passing `{KEY}={VALUE}` pairs to `modal secret create`:

```bash
modal secret create database-secret PGHOST=uri PGPORT=5432 PGUSER=admin PGPASSWORD=hunter2
```

or using environment variables (assuming below that the `PGPASSWORD` environment variable is set
e.g. by your CI system):

```bash
modal secret create database-secret PGHOST=uri PGPORT=5432 PGUSER=admin PGPASSWORD="$PGPASSWORD"
```

Remove Secrets by passing their name to `modal secret delete`:

```bash
modal secret delete database-secret
```
