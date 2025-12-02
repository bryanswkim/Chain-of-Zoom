# Environments

Environments are sub-divisions of workspaces, allowing you to deploy the same app
(or set of apps) in multiple instances for different purposes without changing
your code. Typical use cases for environments include having one `dev`
environment and one `prod` environment, preventing overwriting production apps
when developing new features, while still being able to deploy changes to a
"live" and potentially complex structure of apps.

Each environment has its own set of [Secrets](/docs/guide/secrets) and any
object lookups performed from an app in an environment will by default look for
objects in the same environment.

By default, every workspace has a single Environment called "main". New
Environments can be created on the CLI:

```sh
modal environment create dev
```

(You can run `modal environment --help` for more info)

Workspaces can have up to 1500 Environments.

Once created, Environments show up as a dropdown menu in the navbar of the
[Modal dashboard](/home), letting you set browse all Modal Apps and Secrets
filtered by which Environment they were deployed to.

Most CLI commands also support an `--env` flag letting you specify which
Environment you intend to interact with, e.g.:

```sh
modal run --env=dev app.py
modal volume create --env=dev storage
```

To set a default Environment for your current CLI profile you can use
`modal config set-environment`, e.g.:

```sh
modal config set-environment dev
```

Alternatively, you can set the `MODAL_ENVIRONMENT` environment variable.

## Environment web suffixes

Environments have a 'web suffix' which is used to make
[web endpoint URLs](/docs/guide/webhook-urls) unique across your workspace. One
Environment is allowed to have no suffix (`""`).

## Cross environment lookups

It's possible to explicitly look up objects in Environments other than the Environment
your app runs within:

```python
production_secret = modal.Secret.from_name(
    "my-secret",
    environment_name="main"
)
```

```python notest
modal.Function.from_name(
    "my_app",
    "some_function",
    environment_name="dev"
)
```

However, the `environment_name` argument is optional and omitting it will use
the Environment from the object's associated App or calling context.
