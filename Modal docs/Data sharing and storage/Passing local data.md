# Passing local data

If you have a function that needs access to some data not present in your Python
files themselves you have a few options for bundling that data with your Modal
app.

## Passing function arguments

The simplest and most straight-forward way is to read the data from your local
script and pass the data to the outermost Modal function call:

```python
import json


@app.function()
def foo(a):
    print(sum(a["numbers"]))


@app.local_entrypoint()
def main():
    data_structure = json.load(open("blob.json"))
    foo.remote(data_structure)
```

Any data of reasonable size that is serializable through
[cloudpickle](https://github.com/cloudpipe/cloudpickle) is passable as an
argument to Modal functions.

Refer to the section on [global variables](/docs/guide/global-variables) for how
to work with objects in global scope that can only be initialized locally.

## Including local files

For including local files for your Modal Functions to access, see [Defining Images](/docs/guide/images).
