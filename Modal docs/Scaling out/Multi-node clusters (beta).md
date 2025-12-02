# Multi-node clusters (beta)

> 🚄 Multi-node clusters with RDMA are in **private beta.** Please contact us via the [Modal Slack](https://modal.com/slack) or support@modal.com to get access.

Modal supports running a training job across several coordinated containers. Each container can saturate the available GPU devices on its host (aka node) and communicate with peer containers which do the same. By scaling a training job from a single GPU to 16 GPUs you can achieve nearly 16x improvements in training time.

### Cluster compute capability

Modal H100 clusters provide:

- A 50 Gbps [IPv6 private network](https://modal.com/docs/guide/private-networking) for orchestration, dataset downloading, etc.
- A 3,200 Gbps RDMA scale-out network ([RoCE](https://en.wikipedia.org/wiki/RDMA_over_Converged_Ethernet)).
- Up to 64 H100 SXM devices.
- At least 1 TB of RAM and 4 TB of local NVMe SSD per node.
- Deep burn-in testing.
- Interoperability with all Modal platform functionality ([Volumes](/docs/guide/volumes), [Dicts](/docs/guide/dicts), [Tunnels](/docs/guide/tunnels), etc.).

The guide will walk you through how the Modal client library enables multi-node training and integrates with `torchrun`.

### `@clustered`

Unlike standard Modal Function containers, containers in a multi-node training job must be able to:

1. Perform fast, direct network communication between each other.
2. Be scheduled together, all or nothing, at the same time.

The `@clustered` decorator enables this behavior.

```python
import modal.experimental

@app.function(
    gpu="H100:8",
    timeout=60 * 60 * 24,
    retries=modal.Retries(initial_delay=0.0, max_retries=10),
)
@modal.experimental.clustered(size=4)
def train_model():
    cluster_info = modal.experimental.get_cluster_info()

    container_rank = cluster_info.rank
    world_size = len(cluster_info.container_ips)
    main_addr = cluster_info.container_ips[0]
    is_main = "(main)" if container_rank == 0 else ""

    print(f"{container_rank=} {is_main} {world_size=} {main_addr=}")
    ...
```

Applying this decorator under `@app.function` modifies the Function so that remote calls to it are serviced by a multi-node container group. The above configuration creates a group of four containers each having 8 H100 GPU devices, for a total of 32 devices.

## Scheduling

A `modal.experimental.clustered` Function runs on multiple nodes in our cloud, but executes like a normal function call. For example, all nodes are scheduled together ([gang scheduling](https://en.wikipedia.org/wiki/Gang_scheduling)) so that your code runs on all of the requested hardware or not at all.

Traditionally this kind of cluster and scheduling management would be handled by SLURM, Kubernetes, or manually. But with Modal it's all provided serverlessly with just a Python decorator!

### Rank & input broadcast

![diagram](https://modal-cdn.com/cdnbot/multinodepmgnla70_4b57a155.webp)

You may notice above that a single `.remote` Function call created three input executions but returned only one output. This is how input-output is structured for multi-node training jobs on Modal. The Function call’s arguments are replicated to each container, but only the rank zero container’s is returned to the caller.

A container’s rank is a key concept in multi-node jobs. Rank zero is the 'leader' rank and typically coordinates the job. Rank zero is also known as the "main" container. Rank zero's output will always be the output of a multi-node training run.

## Networking

Function containers cannot normally make direct network connections to other Function containers, but this is a requirement for multi-node training communication. So, along with gang scheduling, the `@clustered` decorator enables Modal’s workspace-private inter-container networking called [i6pn](https://www.notion.so/Multi-node-docs-1281e7f16949806f966adedfe8b2cb74?pvs=21).

The [cluster networking guide](/docs/guide/private-networking) goes into more detail on i6pn, but the upshot is that each container in the cluster is made aware of the network address of all the other containers in the cluster, enabling them to communicate with each other quickly via [TCP](https://pytorch.org/docs/stable/elastic/rendezvous.html).

### RDMA (Infiniband)

H100 clusters are equipped with Infiniband providing up to 3,200 Gbps scale-out bandwidth for inter-node communication.
RDMA scale-out networking is enabled with the `rdma` parameter of `modal.experimental.clustered`.

```python notest
@modal.experimental.clustered(size=2, rdma=True)
def train():
    ...
```

To run a simple Infiniband RDMA performance test see the [this sample code](https://github.com/modal-labs/multinode-training-guide/tree/main/benchmark).

## Cluster Info

`modal.experimental.get_cluster_info()` exposes the following information about the cluster:

- `rank: int` is the current container's order within the cluster, starting from `0`, the leader.
- `container_ips: list[str]` contains the IPv6 addresses of each container in the cluster, sorted by rank.
- `container_ipv4_ips: list[str]` contains the IPv4 addresses of each container in the cluster, sorted by rank.

## Fault Tolerance

For a clustered Function, failures in inputs and containers are handled differently.

If an input fails on any container, this failure **is not propagated** to other containers in the cluster. Containers are responsible for detecting and responding to input failures on other containers.

Only rank 0's output matters: if an input fails on the leader container (rank 0), the input is marked as failed, even if the input succeeds on another container. Similarly, if an input succeeds on the leader container but fails on another container, the input will still be marked as successful.

If a container in the cluster is preempted, Modal will terminate all remaining containers in the cluster, and retry the input.

### Input Synchronization

_**Important:**_ synchronization is not relevant for single training runs, and applies mostly to inference use-cases.

Modal does not synchronize input execution across containers. Containers are responsible for ensuring that they do not process inputs faster than other containers in their cluster.

In particular, it is important that the leader container (rank 0) only starts processing the next input after all other containers have finished processing the current input.

## Examples

To get hands-on with multi-node training you can jump into the [`multinode-training-guide` repository](https://github.com/modal-labs/multinode-training-guide) or [`modal-examples` repository](https://github.com/modal-labs/modal-examples/tree/main/14_clusters) and `modal run` something!

- [Simple ‘hello world’ 4 X 1 H100 torch cluster example](https://github.com/modal-labs/modal-examples/blob/main/14_clusters/simple_torch_cluster.py)
- [Infiniband RDMA performance test](https://github.com/modal-labs/multinode-training-guide/tree/main/benchmark)
- [Use 2 x 8 H100s to train a ResNet50 model on the ImageNet dataset](https://github.com/modal-labs/multinode-training-guide/tree/main/resnet50)
- [Speedrun GPT-2 training with modded-nanogpt](https://github.com/modal-labs/multinode-training-guide/tree/main/nanoGPT)
<!-- - Use 2 x 8 H100s to run multi-node _inference_ on LLaMA 3.1 405B in 16bit precision. **[TODO]** -->

### Torchrun Example

```python
import modal
import modal.experimental

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("torch~=2.5.1", "numpy~=2.2.1")
    .add_local_dir(
        "training", remote_path="/root/training"
    )
)
app = modal.App("example-simple-torch-cluster", image=image)

n_nodes = 4

@app.function(gpu=f"H100:8", timeout=60 * 60 * 24)
@modal.experimental.clustered(size=n_nodes, rdma=True)
def launch_torchrun():
    # import the 'torchrun' interface directly.
    from torch.distributed.run import parse_args, run

    cluster_info = modal.experimental.get_cluster_info()

    run(
        parse_args(
            [
                f"--nnodes={n_nodes}",
                f"--node-rank={cluster_info.rank}",
                f"--master-addr={cluster_info.container_ips[0]}",
                "--nproc-per-node=8",
                "--master-port=1234",
                "training/train.py",
            ]
        )
    )
```
