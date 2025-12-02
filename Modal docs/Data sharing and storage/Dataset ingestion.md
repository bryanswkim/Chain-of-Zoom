# Large dataset ingestion

This guide provides best practices for downloading, transforming, and storing large datasets within
Modal. A dataset is considered large if it contains hundreds of thousands of files and/or is over
100 GiB in size.

These guidelines ensure that large datasets can be ingested fully and reliably.

## Configure your Function for heavy disk usage

Large datasets should be downloaded and transformed using a `modal.Function` and stored
into a `modal.CloudBucketMount`. We recommend backing the latter with a Cloudflare R2 bucket,
because Cloudflare does not charge network egress fees and has lower GiB/month storage costs than AWS S3.

This `modal.Function` should specify a large `timeout` because large dataset processing can take hours,
and it should request a larger ephemeral disk in cases where the dataset being downloaded and processed
is hundreds of GiBs.

```python
@app.function(
    volumes={
        "/mnt": modal.CloudBucketMount(
            "datasets",
            bucket_endpoint_url="https://abc123example.r2.cloudflarestorage.com",
            secret=modal.Secret.from_name("cloudflare-r2-datasets"),
        )
    },
    ephemeral_disk=1000 * 1000,  # 1 TiB
    timeout=60 * 60 * 12,  # 12 hours

)
def download_and_transform() -> None:
    ...
```

### Use compressed archives on Modal Volumes

`modal.Volume`s are designed for storing tens of thousands of individual files,
but not for hundreds of thousands or millions of files.
However they can be still be used for storing large datasets if files are first combined and compressed
in a dataset transformation step before saving them into the Volume.

See the [transforming](#transforming) section below for more details.

## Experimentation

Downloading and transforming large datasets can be fiddly. While iterating on a reliable ingestion program
it is recommended to start a long-running `modal.Function` serving a JupyterHub server so that you can maintain
disk state in the face of application errors.

See the [running Jupyter server within a Modal function](https://github.com/modal-labs/modal-examples/blob/main/11_notebooks/jupyter_inside_modal.py) example as base code.

## Downloading

The raw dataset data should be first downloaded into the container at `/tmp/` and not placed
directly into the mounted volume. This serves a couple purposes.

1. Certain download libraries and tools (e.g. `wget`) perform filesystem operations not supported properly by `CloudBucketMount`.
2. The raw dataset data may need to be transformed before use, in which case it is wasteful to store it permanently.

This snippet shows the basic download-and-copy procedure:

```python notest
import pathlib
import shutil
import subprocess

tmp_path = pathlib.Path("/tmp/imagenet/")
vol_path = pathlib.Path("/mnt/imagenet/")
filename = "imagenet-object-localization-challenge.zip"
# 1. Download into /tmp/
subprocess.run(
    f"kaggle competitions download -c imagenet-object-localization-challenge --path {tmp_path}",
    shell=True,
    check=True
)
vol_path.mkdir(exist_ok=True)
# 2. Copy (without transform) into mounted volume.
shutil.copyfile(tmp_path / filename, vol_path / filename)
```

## Transforming

When ingesting a large dataset it is sometimes necessary to transform it before storage, so that it is in
an optimal format for loading at runtime. A common kind of necessary transform is gzip decompression. Very large
datasets are often gzipped for storage and network transmission efficiency, but gzip decompression (80 MiB/s)
is hundreds of times slower than reading from a solid state drive (SSD)
and should be done once before storage to avoid decompressing on every read against the dataset.

Transformations should be performed after storing the raw dataset in `/tmp/`. Performing transformations almost always increases container disk usage and this is where the [`ephemeral_disk` parameter](/docs/reference/modal.App#function) parameter becomes important. For example, a
100 GiB raw, compressed dataset may decompress to into 500 GiB, occupying 600 GiB of container disk space.

Transformations should also typically be performed against `/tmp/`. This is because

1. transforms can be IO intensive and IO latency is lower against local SSD.
2. transforms can create temporary data which is wasteful to store permanently.

## Examples

The best practices offered in this guide are demonstrated in the [`modal-examples` repository](https://github.com/modal-labs/modal-examples/tree/main/12_datasets).

The examples include these popular large datasets:

- [ImageNet](https://www.image-net.org/), the image labeling dataset that kicked off the deep learning revolution
- [COCO](https://cocodataset.org/#download), the Common Objects in COntext dataset of densely-labeled images
- [LAION-400M](https://laion.ai/blog/laion-400-open-dataset/), the Stable Diffusion training dataset
- Data derived from the [Big "Fantastic" Database](https://bfd.mmseqs.com/),
  [Protein Data Bank](https://www.wwpdb.org/), and [UniProt Database](https://www.uniprot.org/)
  used in training the [RoseTTAFold](https://github.com/RosettaCommons/RoseTTAFold) protein structure model
