# Cloud bucket mounts

The [`modal.CloudBucketMount`](/docs/reference/modal.CloudBucketMount) is a
mutable volume that allows for both reading and writing files from a cloud
bucket. It supports AWS S3, Cloudflare R2, and Google Cloud Storage buckets.

Cloud bucket mounts are built on top of AWS'
[`mountpoint`](https://github.com/awslabs/mountpoint-s3) technology and inherits
its limitations. See the [Limitations and troubleshooting](#limitations-and-troubleshooting) section for more details.

## Mounting Cloudflare R2 buckets

`CloudBucketMount` enables Cloudflare R2 buckets to be mounted as file system
volumes. Because Cloudflare R2 is
[S3-Compatible](https://developers.cloudflare.com/r2/api/s3/api/) the setup is
very similar between R2 and S3. See
[modal.CloudBucketMount](/docs/reference/modal.CloudBucketMount#modalcloudbucketmount)
for usage instructions.

When creating the R2 API token for use with the mount, you need to have the
ability to read, write, and list objects in the specific buckets you will mount.
You do _not_ need admin permissions, and you should _not_ use "Client IP Address
Filtering".

## Mounting Google Cloud Storage buckets

`CloudBucketMount` enables Google Cloud Storage (GCS) buckets to be mounted as file system
volumes. See [modal.CloudBucketMount](/docs/reference/modal.CloudBucketMount#modalcloudbucketmount)
for GCS setup instructions.

## Mounting S3 buckets

`CloudBucketMount` enables S3 buckets to be mounted as file system volumes. To
interact with a bucket, you must have the appropriate IAM permissions configured
(refer to the section on [IAM Permissions](#iam-permissions)).

```python
import modal
import subprocess

app = modal.App()

s3_bucket_name = "s3-bucket-name"  # Bucket name not ARN.
s3_access_credentials = modal.Secret.from_dict({
    "AWS_ACCESS_KEY_ID": "...",
    "AWS_SECRET_ACCESS_KEY": "...",
    "AWS_REGION": "..."
})

@app.function(
    volumes={
        "/my-mount": modal.CloudBucketMount(s3_bucket_name, secret=s3_access_credentials)
    }
)
def f():
    subprocess.run(["ls", "/my-mount"])
```

### Specifying S3 bucket region

Amazon S3 buckets are associated with a single AWS Region. [`Mountpoint`](https://github.com/awslabs/mountpoint-s3) attempts to automatically detect the region for your S3 bucket at startup time and directs all S3 requests to that region. However, in certain scenarios, like if your container is running on an AWS worker in a certain region, while your bucket is in a different region, this automatic detection may fail.

To avoid this issue, you can specify the region of your S3 bucket by adding an `AWS_REGION` key to your Modal secrets, as in the code example above.

### Using AWS temporary security credentials

`CloudBucketMount`s also support AWS temporary security credentials by passing
the additional environment variable `AWS_SESSION_TOKEN`. Temporary credentials
will expire and will not get renewed automatically. You will need to update
the corresponding Modal Secret in order to prevent failures.

You can get temporary credentials with the [AWS CLI](https://aws.amazon.com/cli/) with:

```shell
$ aws configure export-credentials --format env
export AWS_ACCESS_KEY_ID=XXX
export AWS_SECRET_ACCESS_KEY=XXX
export AWS_SESSION_TOKEN=XXX...
```

All these values are required.

### Using OIDC identity tokens

Modal provides [OIDC integration](/docs/guide/oidc-integration) and will automatically generate identity tokens to authenticate to AWS.
OIDC eliminates the need for manual token passing through Modal secrets and is based on short-lived tokens, which limits the window of exposure if a token is compromised.
To use this feature, you must [configure AWS to trust Modal's OIDC provider](/docs/guide/oidc-integration#step-1-configure-aws-to-trust-modals-oidc-provider)
and [create an IAM role that can be assumed by Modal Functions](/docs/guide/oidc-integration#step-2-create-an-iam-role-that-can-be-assumed-by-modal-functions).

Then, you specify the IAM role that your Modal Function should assume to access the S3 bucket.

```python
import modal

app = modal.App()

s3_bucket_name = "s3-bucket-name"
role_arn = "arn:aws:iam::123456789abcd:role/s3mount-role"

@app.function(
    volumes={
        "/my-mount": modal.CloudBucketMount(
            bucket_name=s3_bucket_name,
            oidc_auth_role_arn=role_arn
        )
    }
)
def f():
    subprocess.run(["ls", "/my-mount"])
```

### Mounting a path within a bucket

To mount only the files under a specific subdirectory, you can specify a path prefix using `key_prefix`.
Since this prefix specifies a directory, it must end in a `/`.
The entire bucket is mounted when no prefix is supplied.

```python
import modal
import subprocess

app = modal.App()

s3_bucket_name = "s3-bucket-name"
prefix = 'path/to/dir/'

s3_access_credentials = modal.Secret.from_dict({
    "AWS_ACCESS_KEY_ID": "...",
    "AWS_SECRET_ACCESS_KEY": "...",
})

@app.function(
    volumes={
        "/my-mount": modal.CloudBucketMount(
            bucket_name=s3_bucket_name,
            key_prefix=prefix,
            secret=s3_access_credentials
        )
    }
)
def f():
    subprocess.run(["ls", "/my-mount"])
```

This will only mount the files in the bucket `s3-bucket-name` that are prefixed by `path/to/dir/`.

### Read-only mode

To mount a bucket in read-only mode, set `read_only=True` as an argument.

```python
import modal
import subprocess

app = modal.App()

s3_bucket_name = "s3-bucket-name"  # Bucket name not ARN.
s3_access_credentials = modal.Secret.from_dict({
    "AWS_ACCESS_KEY_ID": "...",
    "AWS_SECRET_ACCESS_KEY": "...",
})

@app.function(
    volumes={
        "/my-mount": modal.CloudBucketMount(s3_bucket_name, secret=s3_access_credentials, read_only=True)
    }
)
def f():
    subprocess.run(["ls", "/my-mount"])
```

While S3 mounts support both write and read operations, they are optimized for
reading large files sequentially. Certain file operations, such as renaming
files, are not supported. For a comprehensive list of supported operations,
consult the
[Mountpoint documentation](https://github.com/awslabs/mountpoint-s3/blob/main/doc/SEMANTICS.md).

### IAM permissions

To utilize `CloudBucketMount` for reading and writing files from S3 buckets,
your IAM policy must include permissions for `s3:PutObject`,
`s3:AbortMultipartUpload`, and `s3:DeleteObject`. These permissions are not
required for mounts configured with `read_only=True`.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ModalListBucketAccess",
      "Effect": "Allow",
      "Action": ["s3:ListBucket"],
      "Resource": ["arn:aws:s3:::<MY-S3-BUCKET>"]
    },
    {
      "Sid": "ModalBucketAccess",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:AbortMultipartUpload",
        "s3:DeleteObject"
      ],
      "Resource": ["arn:aws:s3:::<MY-S3-BUCKET>/*"]
    }
  ]
}
```

## Limitations and troubleshooting

Cloud Bucket Mounts have certain limitations that do not apply to [Volumes](/docs/guide/volumes).
These limitations are primarily around the way that files can be opened and edited in Cloud Bucket Mounts. For
a comprehensive list of limitations, see the [Mountpoint troubleshooting documentation](https://github.com/awslabs/mountpoint-s3/blob/a6179c72bfc237a1fdd06eb4a0863ca537f8d8a7/doc/TROUBLESHOOTING.md)
and the [Mountpoint semantics documentation](https://github.com/awslabs/mountpoint-s3/blob/main/doc/SEMANTICS.md).

The most common issues that users encounter are:

- Files cannot be opened in append mode.
- Files cannot be written to at arbitrary offsets i.e. `seek` and write are not supported together.
- To write to a file, you must open it in `truncate` mode.

These operations typically result in a `PermissionError: [Errno 1] Operation not permitted` error.

If you need these features, give [Volumes](/docs/guide/volumes) a try! If you need these features in S3
and are willing to pay extra for your bucket, you may be able to use [S3 Express](https://aws.amazon.com/s3/storage-classes/express-one-zone/).
Contact us [in our Slack](https://modal.com/slack) if you're interested in using S3 Express.

### Writing files in append mode

If you're using a library which must open a file in append mode, it's best to write to a temporary file
and then move it to your bucket's mount path. A similar approach can be used to write to a file at an arbitrary offset.

```python notest
import tempfile
import shutil

@app.function(
    volumes={"/bucket": modal.CloudBucketMount("my-bucket", secret=s3_credentials)}
)
def append_to_log():
    # Write to a temporary file that supports append mode
    with tempfile.NamedTemporaryFile(mode='a', delete=False) as temp_file:
        temp_file.write("Log entry 1\n")
        temp_file.write("Log entry 2\n")
        temp_path = temp_file.name

    # Move the completed file to the bucket mount
    shutil.move(temp_path, "/bucket/logfile.txt")
```

### Creating a file without a parent directory

If you try to create a file in a directory that doesn't exist, you'll get a `Operation not permitted` error.
To fix this, create the parent directory first with `Path(dst).parent.mkdir(exist_ok=True, parents=True)`.

### Using `np.savez`

`np.savez` seeks to random offsets in a file, making it unsafe for Cloud Bucket Mounts. If your file is large,
you can write it to a temporary file and then move it to your bucket's mount path. If it's small, however,
you can solve this with an in-memory buffer:

```python notest
import io
import numpy as np
import shutil

data = np.random.rand(1000, 512)

# 1. Build the archive entirely in memory
tmp = io.BytesIO()
np.savez_compressed(tmp, array=data)

# 2. Copy it once, sequentially, to the mount point
dest = "/bucket/data.npz"
with open(dest, "wb") as f:
    shutil.copyfileobj(tmp, f)
```

### Torchtune writing checkpoint files

Old versions of [Torchtune](https://github.com/pytorch/torchtune) are incompatible with Cloud Bucket Mounts.
Upgrade to a version greater than or equal to `0.6.1` to ensure checkpoints can be written to the bucket.

### Using the TensorBoard `SummaryWriter`

The TensorBoard `SummaryWriter` opens log files in append mode. These files are quite small, though,
so we recommend writing to a temporary directory and using the [Watchdog](https://github.com/gorakhargosh/watchdog)
Python library to copy the files to the bucket mount path as they come in.

This is a case where it may be worth it to use [Volumes](/docs/guide/volumes) instead - in particular,
training logs are sometimes not subject to the same compliance requirements that force something like checkpoints
or model weights to be stored in a secure location. We even have an example of
[how to use TensorBoard on Volumes](/docs/examples/torch_profiling#serving-tensorboard-on-modal-to-view-pytorch-profiles-and-traces).
