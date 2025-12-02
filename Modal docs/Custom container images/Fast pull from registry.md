# Fast pull from registry

The performance of pulling public and private images from registries into Modal
can be significantly improved by adopting the [eStargz](https://github.com/containerd/stargz-snapshotter/blob/main/docs/estargz.md) compression format.

By applying eStargz compression during your image build and push, Modal will be much
more efficient at pulling down your image from the registry.

## How to use estargz

If you have [Buildkit](https://docs.docker.com/build/buildkit/) version greater than `0.10.0`, adopting `estargz` is as simple as
adding some flags to your `docker buildx build` command:

- `type=registry` flag will instruct BuildKit to push the image after building.
  - If you do not push the image from immediately after build and instead attempt to push it later with docker push, the image will be converted to a standard gzip image.
- `compression=estargz` specifies that we are using the [eStargz](https://github.com/containerd/stargz-snapshotter/blob/main/docs/estargz.md) compression format.
- `oci-mediatypes=true` specifies that we are using the OCI media types, which is required for eStargz.
- `force-compression=true` will recompress the entire image and convert the base image to eStargz if it is not already.

```bash
docker buildx build --tag "<registry>/<namespace>/<repo>:<version>" \
--output type=registry,compression=estargz,force-compression=true,oci-mediatypes=true \
.
```

Then reference the container image as normal in your Modal code.

```python notest
app = modal.App(
    "example-estargz-pull",
    image=modal.Image.from_registry(
        "public.ecr.aws/modal/estargz-example-images:text-generation-v1-esgz"
    )
)
```

At build time you should see the eStargz-enabled puller activate:

```
Building image im-TinABCTIf12345ydEwTXYZ

=> Step 0: FROM public.ecr.aws/modal/estargz-example-images:text-generation-v1-esgz
Using estargz to speed up image pull (index loaded in 1.86s)...
Progress: 10% complete... (1.11s elapsed)
Progress: 20% complete... (3.10s elapsed)
Progress: 30% complete... (4.18s elapsed)
Progress: 40% complete... (4.76s elapsed)
Progress: 50% complete... (5.51s elapsed)
Progress: 62% complete... (6.17s elapsed)
Progress: 74% complete... (6.99s elapsed)
Progress: 81% complete... (7.23s elapsed)
Progress: 99% complete... (8.90s elapsed)
Progress: 100% complete... (8.90s elapsed)
Copying image...
Copied image in 5.81s
```

## Supported registries

Currently, Modal supports fast estargz pulling images with the following registries:

- AWS Elastic Container Registry (ECR)
- Docker Hub (docker.io)
- Google Artifact Registry (gcr.io, pkg.dev)

We are working on adding support for GitHub Container Registry (ghcr.io).
