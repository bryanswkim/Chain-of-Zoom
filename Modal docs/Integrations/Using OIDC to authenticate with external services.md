# Using OIDC to authenticate with external services

Your Functions in Modal may need to access external resources like S3 buckets.
Traditionally, you would need to store long-lived credentials in Modal Secrets
and reference those Secrets in your function code. With the Modal OIDC
integration, you can instead use automatically-generated identity
tokens to authenticate to external services.

## How it works

[OIDC](https://auth0.com/docs/authenticate/protocols/openid-connect-protocol) is
a standard protocol for authenticating users between systems. In Modal, we use
OIDC to generate short-lived tokens that external services can use to verify
that your function is authenticated.

The OIDC integration has two components: the discovery document and the generated
tokens.

The [OIDC discovery document](https://swagger.io/docs/specification/v3_0/authentication/openid-connect-discovery/)
describes how our OIDC server is configured. It primarily includes the supported
[claims](https://developer.okta.com/blog/2017/07/25/oidc-primer-part-1) and the [keys](https://auth0.com/docs/secure/tokens/json-web-tokens/json-web-key-sets)
we use to sign tokens. Discovery documents are always hosted at `/.well-known/openid-configuration`, and
you can view ours at <https://oidc.modal.com/.well-known/openid-configuration>.

The generated tokens are [JWTs](https://jwt.io/) signed by Modal using the keys described in the
discovery document. These tokens contain the full identity of the Function
in the `sub` claim, and they use custom claims to make this information more
easily accessible. See our [discovery document](https://oidc.modal.com/.well-known/openid-configuration)
for a full list of claims.

Generated tokens are injected into your Function's containers via the `MODAL_IDENTITY_TOKEN`
environment variable. Below is an example of what claims might be included in a token:

```json
{
  "sub": "modal:workspace_id:ac-12345abcd:environment_name:modal-examples:app_name:oidc-token-test:function_name:jwt_return_func:container_id:ta-12345abcd",
  "aud": "oidc.modal.com",
  "exp": 1732137751,
  "iat": 1731964951,
  "iss": "https://oidc.modal.com",
  "jti": "31f92dca-e847-4bc9-8d15-9f234567a123",
  "workspace_id": "ac-12345abcd",
  "environment_id": "en-12345abcd",
  "environment_name": "modal-examples",
  "app_id": "ap-12345abcd",
  "app_name": "oidc-token-test",
  "function_id": "fu-12345abcd",
  "function_name": "jwt_return_func",
  "container_id": "ta-12345abcd"
}
```

### Key thumbprints

RSA keys have [thumbprints](https://connect2id.com/products/nimbus-jose-jwt/examples/jwk-thumbprints). You
can use these thumbprints to verify that the keys in our discovery document are
genuine. This protects against potential Man in the Middle (MitM) attacks, although
our required use of HTTPS mitigates this risk.

If you'd like to have the extra security of verifying the thumbprints, you can
use the following command to print the thumbprints for the keys in our
discovery document:

```bash
$ openssl s_client -connect oidc.modal.com:443 < /dev/null 2>/dev/null | openssl x509 -fingerprint -noout | awk -F= '{print $2}' | tr -d ':'
F062F2151EDE30D1620B48B7AC91D66047D769D3
```

Note that these thumbprints may change over time as we rotate keys. We recommend
periodically checking for and updating your scripts with the new thumbprints.

### App name format

By default, Modal Apps can be created with arbitrary names. However, when using
OIDC, the App name has a stricter character set. Specifically, it must be 64
characters or less and can only include alphanumeric characters, dashes, periods,
and underscores. If these constraints are violated, the OIDC token will not be
injected into the container.

Note that these are the same constraints that are applied to [Deployed Apps](/docs/guide/managing-deployments).
This means that if an App is deployable, it will also be compatible with OIDC.

## Demo usage with AWS S3

To see how OIDC tokens can be used, we'll demo a simple Function that lists
objects in an S3 bucket.

### Step 0: Understand your OIDC claims

Before we can configure OIDC policies, we need to know what claims we can match
against. We can run a Function and inspect its claims to find out.

```python notest
app = modal.App("oidc-token-test")

jwt_image = modal.Image.debian_slim().pip_install("pyjwt")

@app.function(image=jwt_image)
def jwt_return_func():
    import jwt

    token = os.environ["MODAL_IDENTITY_TOKEN"]
    claims = jwt.decode(token, options={"verify_signature": False})
    print(json.dumps(claims, indent=2))

@app.local_entrypoint()
def main():
    jwt_return_func.remote()
```

Run the function locally to see its claims:

```bash
$ modal run oidc-token-test.py
{
  "sub": "modal:workspace_id:ac-12345abcd:environment_name:modal-examples:app_name:oidc-token-test:function_name:jwt_return_func:container_id:ta-12345abcd",
  "aud": "oidc.modal.com",
  "exp": 1732137751,
  "iat": 1731964951,
  "iss": "https://oidc.modal.com",
  "jti": "31f92dca-e847-4bc9-8d15-9f234567a123",
  "workspace_id": "ac-12345abcd",
  "environment_id": "en-12345abcd",
  "environment_name": "modal-examples",
  "app_id": "ap-12345abcd",
  "app_name": "oidc-token-test",
  "function_id": "fu-12345abcd",
  "function_name": "jwt_return_func",
  "container_id": "ta-12345abcd"
}
```

Now we can match off these claims to configure our OIDC policies.

### Step 1: Configure AWS to trust Modal's OIDC provider

We need to make AWS accept Modal identity tokens. To do this, we need to add
Modal's OIDC provider as a trusted entity in our AWS account.

```bash
aws iam create-open-id-connect-provider \
    --url https://oidc.modal.com \
    --client-id-list oidc.modal.com \
    # Optionally replace with the thumbprint from the discovery document.
    # Note that this may change over time as we rotate keys, and this argument
    # can be omitted if you'd prefer to rely on the HTTPS verification instead.
    --thumbprint-list "<thumbprint>"
```

This will trigger AWS to pull down our [JSON Web Key Set (JWKS)](https://auth0.com/docs/secure/tokens/json-web-tokens/json-web-key-sets)
and use it to verify the signatures of any tokens signed by Modal.

### Step 2: Create an IAM policy that can be used by Modal Functions

Let's create a simple IAM policy that allows listing objects in an S3 bucket.
Take the policy below and replace the bucket name with your own.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:GetObject", "s3:ListBucket"],
      "Resource": ["arn:aws:s3:::fun-bucket", "arn:aws:s3:::fun-bucket/*"]
    }
  ]
}
```

### Step 3: Create an IAM role that can be assumed by Modal Functions

Now, we can create an IAM role that uses this policy. Visit the IAM console
to create this role. If you add this policy using the CLI, update the
OIDC provider ARN to match the one created in [Step 1](#step-1-configure-aws-to-trust-modals-oidc-provider).
Be sure to replace the Workspace ID placeholder with your own. You can find your Workspace ID
using the script from [Step 0](#step-0-understand-your-oidc-claims).

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::123456789abcd:oidc-provider/oidc.modal.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "oidc.modal.com:aud": "oidc.modal.com"
        },
        "StringLike": {
          "oidc.modal.com:sub": "modal:workspace_id:ac-12345abcd:*"
        }
      }
    }
  ]
}
```

Note how we use `workspace_id` to limit the scope of the role. This means that
the IAM role can only be assumed by Functions in your Workspace. You can further
limit this by specifying an Environment, App, or Function name.

Ideally, we would use the custom claims for role limiting. Unfortunately, AWS
does not support [matching on custom claims](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_iam-condition-keys.html#condition-keys-wif),
so we use the `sub` claim instead.

### Step 4: Use the OIDC token in your Function

The AWS SDKs have built-in support for OIDC tokens, so you can use them as
follows:

```python notest
import boto3

app = modal.App("oidc-token-test")

boto3_image = modal.Image.debian_slim().pip_install("boto3")

# Trade a Modal OIDC token for AWS credentials
def get_s3_client(role_arn):
    sts_client = boto3.client("sts")

    # Assume role with Web Identity
    credential_response = sts_client.assume_role_with_web_identity(
        RoleArn=role_arn, RoleSessionName="OIDCSession", WebIdentityToken=os.environ["MODAL_IDENTITY_TOKEN"]
    )

    # Extract credentials
    credentials = credential_response["Credentials"]
    return boto3.client(
        "s3",
        aws_access_key_id=credentials["AccessKeyId"],
        aws_secret_access_key=credentials["SecretAccessKey"],
        aws_session_token=credentials["SessionToken"],
    )

# List the contents of an S3 bucket
@app.function(image=boto3_image)
def list_bucket_contents(bucket_name, role_arn):
    s3_client = get_s3_client(role_arn)
    response = s3_client.list_objects_v2(Bucket=bucket_name)
    for obj in response["Contents"]:
        print(f"- {obj['Key']} (Size: {obj['Size']} bytes)")

@app.local_entrypoint()
def main():
    # Replace with the role ARN and bucket name from step 2
    list_bucket_contents.remote("fun-bucket", "arn:aws:iam::123456789abcd:role/oidc_test_role")
```

Run the function locally to see the contents of the bucket:

```bash
$ modal run oidc-token-test.py
- test-file.txt (Size: 10 bytes)
```

## Demo usage with AWS Elastic Container Registry (ECR)

You can also use OIDC to authenticate [Private Registries](/docs/guide/existing-images) on AWS.

### Prerequisites

1. Configure AWS to trust Modal's OIDC provider ([Step 1 above](#step-1-configure-aws-to-trust-modals-oidc-provider))

2. [Create an AWS Policy with read-only ECR access](/docs/guide/existing-images#elastic-container-registry-ecr)

3. Create an IAM role that uses this policy ([Step 3 above](#step-3-create-an-iam-role-that-can-be-assumed-by-modal-functions))

### Test with a sample image

Create sample Dockerfile:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
CMD ["python3"]
```

Build and push the image to ECR:

```bash
# Login with the AWS CLI
aws ecr get-login-password --region [ECR_REGION] | docker login --username AWS --password-stdin [ECR_REPO_ARN]

# Build the Docker Image
docker build -t modal-oidc-test-image .

# Push the image to ECR
docker tag modal-oidc-test-image:latest [ECR_REPO_ARN]:latest
docker push [ECR_REPO_ARN]:latest
```

Test pulling the image from ECR:

```python
import modal

app = modal.App("image-from-ecr-test")
sample_image = modal.Image.from_aws_ecr(
    "[ECR_IMAGE_URI]", #eg. "12345678.dkr.ecr.us-east-1.amazonaws.com/repository:latest"
    secret=modal.Secret.from_dict(
        {
            "AWS_ROLE_ARN": "[IAM_ROLE_ARN]", # eg. "arn:aws:iam::123456789abcd:role/oidc_test_role"
            "AWS_REGION": "[ECR_REGION]", # eg. "us-east-1"
        }
    ),
)

@app.function(image=sample_image)
def hello():
    print("Hello, World!")
```

## Next steps

The OIDC integration can be used for much more than just AWS. With this same pattern,
you can configure automatic access to [Vault](https://developer.hashicorp.com/vault/docs/auth/jwt),
[GCP](https://cloud.google.com/identity-platform/docs/web/oidc), [Azure](https://learn.microsoft.com/en-us/entra/identity-platform/v2-protocols-oidc), and more.
At this time, OIDC-authenticated container image pulling is only support with AWS ECR.
