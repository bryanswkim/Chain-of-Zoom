# Region selection

Modal allows you to specify which cloud region you would like to run a Function in. This may be useful if:

- you are required (for regulatory reasons or by your customers) to process data within certain regions.
- you want to reduce egress fees that result from reading data from a dependency like S3.
- you have a latency-sensitive app where app endpoints need to run near an external DB.

Note that regardless of what region your Function runs in, all Function inputs and outputs go through Modal's control plane in us-east-1.

## Pricing

A multiplier on top of our [base usage pricing](/pricing) will be applied to any function that has a cloud region defined.

| **Region**             | **Multiplier** |
| ---------------------- | -------------- |
| Any region in US/EU/AP | 1.25x          |
| All other regions      | 2.5x           |

Here's an example: let's say you have a function that uses 1 T4, 1 CPU core, and 1GB memory. You've specified that the function should run in `us-east-2`. The cost to run this function for 1 hour would be `((T4 hourly cost) + (CPU hourly cost for one core) + (Memory hourly cost for one GB)) * 1.25`.

If you specify multiple regions and they span the two categories above, we will apply the smaller of the two multipliers.

## Specifying a region

To run your Modal Function in a specific region, pass a `region=` argument to the `function` decorator.

```python
import os
import modal

app = modal.App("...")

@app.function(region="us-east") # also supports a list of options, for example region=["us-central", "us-east"]
def f():
    print(f"running in {os.environ['MODAL_REGION']}") # us-east-1, us-east-2, us-ashburn-1, etc.
```

You can specify a region in addition to the underlying cloud, `@app.function(cloud="aws", region="us-east")` would run your Function only in `"us-east-1"` or `"us-east-2"` for instance.

## Region options

Modal offers varying levels of granularity for regions. Use broader regions when possible, as this increases the pool of available resources your Function can be assigned to, which improves cold-start time and availability.

### United States ("us")

Use `region="us"` to select any region in the United States.

<!-- TODO: auto-generate this table, this is not sustainable -->

```
     Broad            Specific             Description
 ==============================================================
  "us-east"           "us-east-1"          AWS Virginia
                      "us-east-2"          AWS Ohio
                      "us-east1"           GCP South Carolina
                      "us-east4"           GCP Virginia
                      "us-east5"           GCP Ohio
                      "us-ashburn-1"       OCI Virginia
                      "eastus"             AZR Virginia
                      "eastus2"            AZR Virginia
 --------------------------------------------------------------
  "us-central"        "us-central1"        GCP Iowa
                      "us-chicago-1"       OCI Chicago
                      "us-phoenix-1"       OCI Phoenix
                      "centralus"          AZR Iowa
                      "northcentralus"     AZR Illinois
                      "southcentralus"     AZR Texas
                      "westcentralus"      AZR Wyoming
 --------------------------------------------------------------
  "us-west"           "us-west-1"          AWS California
                      "us-west-2"          AWS Oregon
                      "us-west1"           GCP Oregon
                      "us-west3"           GCP Utah
                      "us-west4"           GCP Nevada
                      "us-sanjose-1"       OCI San Jose
                      "westus"             AZR California
                      "westus2"            AZR Washington
                      "westus3"            AZR Phoenix
```

### Europe ("eu")

Use `region="eu"` to select any region in Europe.

```
     Broad            Specific             Description
 ==============================================================
  "eu-west"           "eu-central-1"       AWS Frankfurt
                      "eu-west-1"          AWS Ireland
                      "eu-west-3"          AWS Paris
                      "europe-west1"       GCP Belgium
                      "europe-west3"       GCP Frankfurt
                      "europe-west4"       GCP Netherlands
                      "eu-frankfurt-1"     OCI Frankfurt
                      "eu-paris-1"         OCI Paris
                      "francecentral"      AZR Paris
                      "germanywestcentral" AZR Frankfurt
                      "switzerlandnorth"   AZR Zurich
                      "westeurope"         AZR Netherlands
 --------------------------------------------------------------
  "eu-north"          "eu-north-1"         AWS Stockholm
                      "swedencentral"      AZR Gävle
                      "northeurope"        AZR Ireland
                      "norwayeast"         AZR Norway
```

### Asia–Pacific ("ap")

Use `region="ap"` to select any region in Asia–Pacific.

```
     Broad            Specific             Description
 ==============================================================
  "ap-northeast"      "asia-northeast3"    GCP Seoul
                      "asia-northeast1"    GCP Tokyo
                      "ap-northeast-1"     AWS Tokyo
                      "ap-northeast-3"     AWS Osaka
                      "koreacentral"       AZR Seoul
                      "japaneast"          AZR Tokyo, Saitama
                      "japanwest"          AZR Osaka
 --------------------------------------------------------------
  "ap-southeast"      "asia-southeast1"    GCP Singapore
                      "ap-southeast-3"     AWS Jakarta
                      "southeastasia"      AZR Singapore
 --------------------------------------------------------------
  "ap-south"          "ap-south-1"         AWS Mumbai
                      "centralindia"       AZR Pune
                      "westindia"          AZR Mumbai
```

### Other regions

```
     Broad            Specific             Description
 ==============================================================
  "ca"                "ca-central-1"       AWS Montreal
                      "ca-toronto-1"       OCI Toronto
                      "canadacentral"      AZR Toronto
                      "canadaeast"         AZR Quebec
 --------------------------------------------------------------
  "uk"                "uk-london-1"        OCI London
                      "europe-west2"       GCP London
                      "eu-west-2"          AWS London
                      "uksouth"            AZR London
 --------------------------------------------------------------
  "jp"                "ap-northeast-1"     AWS Tokyo
                      "ap-northeast-3"     AWS Osaka
                      "asia-northeast1"    GCP Tokyo
                      "japaneast"          AZR Tokyo, Saitama
                      "japanwest"          AZR Osaka
 --------------------------------------------------------------
  "me"                "me-west1"           GCP Tel Aviv
                      "uaenorth"           AZR Dubai
 --------------------------------------------------------------
  "sa"                "sa-east-1"          AWS São Paulo
                      "brazilsouth"        AZR São Paulo State
 --------------------------------------------------------------
  "au"                "ap-melbourne-1"     OCI Melbourne
                      "ap-sydney-1"        OCI Sydney
                      "australiaeast"      AZR New South Wales
 --------------------------------------------------------------
  "af"                "southafricanorth"   AZR Johannesburg
```

## Region selection and GPU availability

Region selection limits the pool of instances we can run your Functions on. As a result, you may observe higher wait times between when your Function is called and when it gets executed. Generally, we have higher availability in US/EU versus other regions. Whenever possible, select the broadest possible regions so you get the best resource availability.
