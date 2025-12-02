# Using existing images

This guide walks you through how to use an existing container image as a Modal Image.

```python notest
sklearn_image = modal.Image.from_registry("huanjason/scikit-learn")
custom_image = modal.Image.from_dockerfile("./src/Dockerfile")
```

## Load an image from a public registry with `.from_registry`

To load an image from a public registry, just pass the image name, including any tags, to [`Image.from_registry`](/docs/reference/modal.Image#from_registry):

```python
sklearn_image = modal.Image.from_registry("huanjason/scikit-learn")


@app.function(image=sklearn_image)
def fit_knn():
    from sklearn.neighbors import KNeighborsClassifier
    ...
```

The `from_registry` method can load images from all public registries, such as
[Nvidia's `nvcr.io`](https://catalog.ngc.nvidia.com/containers),
[AWS ECR](https://aws.amazon.com/ecr/), and
[GitHub's `ghcr.io`](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry).

You can further modify the image [just like any other Modal Image](/docs/guide/images):

```python continuation
data_science_image = sklearn_image.uv_pip_install("polars", "datasette")
```

You can use external images so long as

- The image is built for the
  [`linux/amd64` platform](https://unix.stackexchange.com/questions/53415/why-are-64-bit-distros-often-called-amd64)
- The image has a [compatible `ENTRYPOINT`](#entrypoint)

Additionally, to be used with a Modal Function, the image needs to have `python` and `pip`
installed and available on the `$PATH`.
If an existing image does not have either `python` or `pip` set up compatibly, you
can still use it. Just provide a version number as the `add_python` argument to
install a reproducible
[standalone build](https://github.com/indygreg/python-build-standalone)
of Python:

```python
ubuntu_image = modal.Image.from_registry("ubuntu:22.04", add_python="3.11")
valhalla_image = modal.Image.from_registry("gisops/valhalla:latest", add_python="3.12")
```

There are some additional restrictions for older versions of the Modal image builder.
Image builder version is set at a workspace level via the settings page [here](/settings/image-config).
See the migration guides on that page for details on any additional restrictions on images.

## Load images from private registries

You can also use images defined in private container registries on Modal.
The exact method depends on the registry you are using.

### Docker Hub (Private)

To pull container images from private Docker Hub repositories,
[create an access token](https://docs.docker.com/security/for-developers/access-tokens/)
with "Read-Only" permissions and use this token value and your Docker Hub
username to create a Modal [Secret](/docs/guide/secrets).

```
REGISTRY_USERNAME=my-dockerhub-username
#REGISTRY_PASSWORD=<insert your password>
```

Use this Secret with the
[`modal.Image.from_registry`](/docs/reference/modal.Image#from_registry) method.

### Elastic Container Registry (ECR)

You can pull images from your AWS ECR account by specifying the full image URI
as follows:

```python
import modal

aws_secret = modal.Secret.from_name("my-aws-secret")
image = (
    modal.Image.from_aws_ecr(
        "000000000000.dkr.ecr.us-east-1.amazonaws.com/my-private-registry:latest",
        secret=aws_secret,
    )
    .pip_install("torch", "huggingface")
)

app = modal.App(image=image)
```

As shown above, you also need to use a [Modal Secret](/docs/guide/secrets)
containing the environment variables `AWS_ACCESS_KEY_ID`,
`AWS_SECRET_ACCESS_KEY`, and `AWS_REGION`. The AWS IAM user account associated
with those keys must have access to the private registry you want to access.

Alternatively, you can use [OIDC token authentication](/docs/guide/oidc-integration#pull-images-from-aws-elastic-container-registry-ecr).

The user needs to have the following read-only policies:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Action": ["ecr:GetAuthorizationToken"],
      "Effect": "Allow",
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer",
        "ecr:GetRepositoryPolicy",
        "ecr:DescribeRepositories",
        "ecr:ListImages",
        "ecr:DescribeImages",
        "ecr:BatchGetImage",
        "ecr:GetLifecyclePolicy",
        "ecr:GetLifecyclePolicyPreview",
        "ecr:ListTagsForResource",
        "ecr:DescribeImageScanFindings"
      ],
      "Resource": "<MY-REGISTRY-ARN>"
    }
  ]
}
```

You can use the IAM configuration above as a template for creating an IAM user.
You can then
[generate an access key](https://aws.amazon.com/premiumsupport/knowledge-center/create-access-key/)
and create a Modal Secret using the AWS integration option. Modal will use your
access keys to generate an ephemeral ECR token. That token is only used to pull
image layers at the time a new image is built. We don't store this token but
will cache the image once it has been pulled.

Images on ECR must be private and follow
[image configuration requirements](/docs/reference/modal.Image#from_aws_ecr).

### Google Artifact Registry and Google Container Registry

For further detail on how to pull images from Google's image registries, see
[`modal.Image.from_gcp_artifact_registry`](/docs/reference/modal.Image#from_gcp_artifact_registry).

## Bring your own image definition with `.from_dockerfile`

You can define an Image from an existing Dockerfile by passing its path to
[`Image.from_dockerfile`](/docs/reference/modal.Image#from_dockerfile):

```python
dockerfile_image = modal.Image.from_dockerfile("Dockerfile")


@app.function(image=dockerfile_image)
def fit():
    import sklearn
    ...
```

Note that you can still extend this Image using image builder methods!
See [the guide](/docs/guide/images) for details.

### Dockerfile command compatibility

Since Modal doesn't use Docker to build containers, we have our own
implementation of the
[Dockerfile specification](https://docs.docker.com/engine/reference/builder/).
Most Dockerfiles should work out of the box, but there are some differences to
be aware of.

First, a few minor Dockerfile commands and flags have not been implemented yet.
These include `ONBUILD`, `STOPSIGNAL`, and `VOLUME`.
Please reach out to us if your use case requires any of these.

Next, there are some command-specific things that may be useful when porting a
Dockerfile to Modal.

#### `ENTRYPOINT`

While the
[`ENTRYPOINT`](https://docs.docker.com/engine/reference/builder/#entrypoint)
command is supported, there is an additional constraint to the entrypoint script
provided: when used with a Modal Function, it must also `exec` the arguments passed to it at some point.
This is so the Modal Function runtime's Python entrypoint can run after your own. Most entrypoint
scripts in Docker containers are wrappers over other scripts, so this is likely
already the case.

If you wish to write your own entrypoint script, you can use the following as a
template:

```bash
#!/usr/bin/env bash

# Your custom startup commands here.

exec "$@" # Runs the command passed to the entrypoint script.
```

If the above file is saved as `/usr/bin/my_entrypoint.sh` in your container,
then you can register it as an entrypoint with
`ENTRYPOINT ["/usr/bin/my_entrypoint.sh"]` in your Dockerfile, or with
[`entrypoint`](/docs/reference/modal.Image#entrypoint) as an
Image build step.

```python
import modal

image = (
    modal.Image.debian_slim()
    .pip_install("foo")
    .entrypoint(["/usr/bin/my_entrypoint.sh"])
)
```

#### `ENV`

We currently don't support default values in
[interpolations](https://docs.docker.com/compose/compose-file/12-interpolation/),
such as `${VAR:-default}`
