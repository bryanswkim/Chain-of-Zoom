# Jupyter notebooks

> **Note:** This page is about running Jupyter on Modal. For our hosted notebooks product with real-time collaboration, see [Modal Notebooks](/docs/guide/notebooks).

You can use the Modal client library in notebook environments like Jupyter! Just
`import modal` and use as normal. You will likely need to use [`app.run`](/docs/guide/apps#ephemeral-apps) to create an ephemeral app to run your functions:

```python,notest
# Cell 1

import modal

app = modal.App()

@app.function()
def my_function(x):
    ...

# Cell 2

with modal.enable_output():
    with app.run():
        my_function.remote(42)
```

## Known issues

- **Interactive shell and interactive functions are not supported.**

  These can only be run within a live terminal session, so they are not
  supported in notebooks.

- **Local and remote Python versions must match.**

  When defining Modal Functions in a Jupyter notebook, the Function automatically
  has `serialized=True` set. This implies that the versions of Python and any third-
  party libraries used in your Modal container must match the version you have locally,
  so that the function can be deserialized remotely without errors.

If you encounter issues not documented above, try restarting the notebook kernel, as it may be
in a broken state, which is common in notebook development.

If the issue persists, contact us [in our Slack](https://modal.com/slack).

We are working on removing these known issues so that writing Modal applications
in a notebook feels just like developing in regular Python modules and scripts.

## Jupyter inside Modal

You can run Jupyter in Modal using the `modal launch` command. For example:

```
$ modal launch jupyter --gpu a10g
```

That will start a Jupyter instance with an A10G GPU attached. You'll be able to
access the app with via a
[Modal Tunnel URL](https://modal.com/docs/guide/tunnels#tunnels-beta). Jupyter
will stop running whenever you stop Modal call in your terminal.

See `--help` for additional options.

## Further examples

- [Basic demonstration of running Modal in a notebook](https://github.com/modal-labs/modal-examples/blob/main/11_notebooks/basic.ipynb)
- [Running Jupyter server within a Modal function](https://github.com/modal-labs/modal-examples/blob/main/11_notebooks/jupyter_inside_modal.py)
