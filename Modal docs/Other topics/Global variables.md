# Global variables

There are cases where you might want objects or data available in **global**
scope. For example:

- You need to use the data in a scheduled function (scheduled functions don't
  accept arguments)
- You need to construct objects (e.g. Secrets) in global scope to use as
  function annotations
- You don't want to clutter many function signatures with some common arguments
  they all use, and pass the same arguments through many layers of function
  calls.

For these cases, you can use the `modal.is_local` function, which returns `True`
if the app is running locally (initializing) or `False` if the app is executing
in the cloud.

For instance, to create a [`modal.Secret`](/docs/guide/secrets) that you can pass
to your function decorators to create environment variables, you can run:

```python
import os

if modal.is_local():
    pg_password = modal.Secret.from_dict({"PGPASS": os.environ["MY_LOCAL_PASSWORD"]})
else:
    pg_password = modal.Secret.from_dict({})


@app.function(secrets=[pg_password])
def get_secret_data():
    connection = psycopg2.connect(password=os.environ["PGPASS"])
    ...
```

## Warning about regular module globals

If you try to construct a global in module scope using some local data _without_
using something like `modal.is_local`, it might have unexpected effects since
your Python modules will be not only be loaded on your local machine, but also
on the remote worker.

E.g., this will typically not work:

```python notest
# blob.json doesn't exist on the remote worker, so this will cause an error there
data_blob = open("blob.json", "r").read()

@app.function()
def foo():
    print(data_blob)
```
