# S3 Gateway endpoints

When running workloads in AWS, our system automatically uses a corresponding
[S3 Gateway endpoint](https://docs.aws.amazon.com/vpc/latest/privatelink/vpc-endpoints-s3.html)
to ensure low costs, optimal performance, and network reliability between Modal and S3.

Workloads running on Modal should not incur egress or ingress fees associated
with S3 operations. No configuration is needed in order for your app to use S3 Gateway endpoints.
S3 Gateway endpoints are automatically used when your app runs on AWS.

## Endpoint configuration

Only use the region-specific endpoint (`s3.<region>.amazonaws.com`) or the
global AWS endpoint (`s3.amazonaws.com`). Using an S3 endpoint from one region
in another **will not use the S3 Gateway Endpoint incurring networking costs**.

Avoid specifying regional endpoints manually, as this can lead to unexpected cost
or performance degradation.

## Inter-region costs

S3 Gateway endpoints guarantee no costs for network traffic within the same AWS region.
However, if your Modal Function runs in one region but your bucket resides in a
different region you will be billed for inter-region traffic.

You can prevent this by scheduling your Modal App in the same region of your
S3 bucket with [Region selection](https://modal.com/docs/guide/region-selection#region-selection).
