# Geographic Latency

Modal's worker cluster is multi-cloud and multi-region. The vast majority of workers are located
in the continental USA, but we do run workers in Europe and Asia.

Modal's control plane is hosted in Virginia, USA (`us-east-1`).

Any time data needs to travel between the Modal client, our control plane servers, and our workers
latency will be incurred. [Cloudping.co](https://www.cloudping.co) provides good estimates on the
significance of the latency between regions. For example, the roundtrip latency between AWS `us-east-1` (Virginia, USA) and
`us-west-1` (California, USA) is around 60ms.

You can observe the location identifier of a container [via an environment variable](/docs/guide/environment_variables).
Logging this environment variable alongside latency information can reveal when geography is impacting your application
performance.

## Region selection

In cases where low-latency communication is required between your container and a network dependency (e.g a database),
it is useful to ensure that Modal schedules your container in only regions geographically proximate to that dependency.
For example, if you have an AWS RDS database in Virginia, USA (`us-east-1`), ensuring your Modal containers are also scheduled in Virginia
means that network latency between the container and the database will be less than 5 milliseconds.

For more information, please see [Region selection](/docs/guide/region-selection).
