# Environment variables

The Modal runtime sets several environment variables during initialization. The
keys for these environment variables are reserved and cannot be overridden by
your Function or Sandbox configuration.

These variables provide information about the containers's runtime
environment.

## Container runtime environment variables

The following variables are present in every Modal container:

- **`MODAL_CLOUD_PROVIDER`** — Modal executes containers across a number of cloud
  providers ([AWS](https://aws.amazon.com/), [GCP](https://cloud.google.com/),
  [OCI](https://www.oracle.com/cloud/)). This variable specifies which cloud
  provider the Modal container is running within.
- **`MODAL_IMAGE_ID`** — The ID of the
  [`modal.Image`](/docs/reference/modal.Image) used by the Modal container.
- **`MODAL_REGION`** — This will correspond to a geographic area identifier from
  the cloud provider associated with the Modal container (see above). For AWS, the
  identifier is a "region". For GCP it is a "zone", and for OCI it is an
  "availability domain". Example values are `us-east-1` (AWS), `us-central1`
  (GCP), `us-ashburn-1` (OCI). See the [full list here](/docs/guide/region-selection#region-options).
- **`MODAL_TASK_ID`** — The ID of the container running the Modal Function or Sandbox.

## Function runtime environment variables

The following variables are present in containers running Modal Functions:

- **`MODAL_ENVIRONMENT`** — The name of the
  [Modal Environment](/docs/guide/environments) the container is running within.
- **`MODAL_IS_REMOTE`** - Set to '1' to indicate that Modal Function code is running in
  a remote container.
- **`MODAL_IDENTITY_TOKEN`** — An [OIDC token](/docs/guide/oidc-integration)
  encoding the identity of the Modal Function.

## Sandbox environment variables

The following variables are present within [`modal.Sandbox`](/docs/reference/modal.Sandbox) instances.

- **`MODAL_SANDBOX_ID`** — The ID of the Sandbox.

## Container image environment variables

The container image layers used by a `modal.Image` may set
environment variables. These variables will be present within your container's runtime
environment. For example, the
[`debian_slim`](/docs/reference/modal.Image#debian_slim) image sets the
`GPG_KEY` variable.

To override image variables or set new ones, use the
[`.env`](https://modal.com/docs/reference/modal.Image#env) method provided by
`modal.Image`.
