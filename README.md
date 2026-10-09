# Quant Research Platform

A proof-of-concept quantitative research platform built on AWS ParallelCluster, Slurm, EC2 Spot, S3, Terraform, and Python.

The project demonstrates an end-to-end research workflow: ingest daily equity data, validate and normalize it, partition it as Parquet, generate a reproducible experiment manifest, run parameterized moving-average backtests, and store results in S3. It also includes a checkpoint-aware Slurm workload used to test recovery after compute-node failure.

> **Status:** the POC experiments are complete and the AWS resources have been destroyed. The repository remains as a reproducible record of the infrastructure, data pipeline, backtest, and resilience test.

## What this project demonstrates

- Infrastructure provisioned with Terraform rather than created manually.
- An AWS ParallelCluster deployment using Slurm as the scheduler.
- An On-Demand head node with an elastic Spot compute fleet that scales from zero to two workers.
- Least-privilege, role-based access to a private, encrypted, versioned S3 bucket.
- A layered market-data pipeline: raw CSV, normalized CSV, and year-partitioned Parquet.
- A deterministic 125-experiment research manifest.
- Parameterized moving-average crossover backtests with timing and performance metrics.
- Slurm job arrays, job requeue, application checkpoints, and final results stored outside disposable workers.
- Two failure-injection approaches and the operational difference between them:
  - a controlled Slurm `DOWN` transition produced 8 of 8 results and resumed affected work from S3 checkpoints.
  - direct EC2 termination produced 6 of 8 expected results;

## Architecture

```text
Developer workstation
  |
  | Terraform / SSH / Git
  v
AWS account (ap-southeast-1)
  |
  +-- Terraform remote state
  |     S3 backend with encryption and lockfile-based state locking
  |
  +-- VPC 
        |
        +-- Public subnet 
        |     |
        |     +-- ParallelCluster head node
        |     |     t3.small, Ubuntu 24.04, On-Demand
        |     |     Slurm controller + shared /home
        |     |
        |     +-- Slurm partition: spot
        |           0-2 x t3.small Spot workers
        |           public IPs enabled for this POC
        |
        +-- Internet gateway and public default route
        +-- S3 gateway VPC endpoint
        |
        +-- Private S3 research-data bucket
              raw/          source CSV
              normalized/   validated CSV
              curated/      symbol/year-partitioned Parquet
              manifests/    experiment definitions
              checkpoints/  resumable task progress
              results/      backtest and resilience outputs
```

The core design principle is that compute is disposable while data, results, and recovery state are durable. ParallelCluster replaces capacity, Slurm schedules or requeues work, and Python restores application progress from S3.

## Repository structure

```text
.
├── infrastructure/
│   ├── backend.tf                  # Encrypted S3 Terraform backend
│   ├── iam.tf                      # Spot service role and research-data IAM
│   ├── locals.tf                   # Resource naming
│   ├── networking.tf               # VPC, subnet, routing, S3 endpoint
│   ├── outputs.tf                  # Cluster and bucket outputs
│   ├── parallelcluster.tf          # ParallelCluster API and cluster config
│   ├── providers.tf                # Terraform and provider constraints
│   ├── storage.tf                  # Versioned/encrypted/private S3 bucket
│   ├── variables.tf
│   └── terraform.tfvars.example
├── slurm/jobs/
│   └── resilience_test.sh          # Eight-task checkpoint/restart experiment
├── src/
│   ├── backtest/backtest.py        # Moving-average crossover backtest
│   ├── common/config.py            # Shared symbols and bucket configuration
│   ├── ingestion/ingest.py         # yfinance to raw S3 CSV
│   ├── normalization/normalize.py  # Schema normalization and validation
│   ├── orchestration/
│   │   ├── generate_manifest.py    # 125-job experiment manifest
│   │   └── resilient_worker.py     # Chunked, checkpoint-aware worker
│   ├── partitioning/partition.py   # CSV to year-partitioned Parquet
│   └── reconciliation/reconcile.py # Placeholder; not yet implemented
├── requirements.txt
└── README.md
```

## AWS infrastructure decisions

### Terraform and state

Terraform `>= 1.10.0` is required. The configuration pins the AWS provider to `~> 6.0`, the AWS ParallelCluster provider to `~> 1.2`, and the ParallelCluster API module to `1.2.0`.

State is stored in an encrypted S3 backend:

```text
bucket: kaviyan-tf-state
key:    quant-research-platform/dev/terraform.tfstate
region: ap-southeast-1
```

The backend uses S3 lockfile-based state locking. The state bucket is assumed to exist before `terraform init`; it is intentionally not created by this configuration.

### Networking

The POC creates:

- one VPC
- one public subnet
- automatic public IP assignment in that subnet;
- an internet gateway and `0.0.0.0/0` public route; and
- an S3 gateway endpoint associated with the public route table.

Both the head node and compute queue use the public subnet. The head node receives an additional security group that permits SSH only from `admin_cidr` and allows all outbound traffic.

This design kept the POC small and avoided NAT gateway cost. For production, compute nodes should normally be placed in private subnets with controlled egress and additional VPC endpoints as required.

### IAM and secrets

The project uses IAM roles and temporary instance credentials rather than static AWS keys on EC2.

Terraform creates a compute role and instance profile with permission to:

- list the research bucket; and
- get and put objects in that bucket.

The ParallelCluster configuration also grants the head and compute nodes read/write S3 access through its `S3Access` configuration. The EC2 Spot service-linked role is created explicitly because the account needed it before Spot capacity could launch.

The SSH key pair is registered from `~/.ssh/id_ed25519.pub`; only the public key is uploaded to AWS. During the POC, the head node used a separate read-only GitHub deploy key so the developer's personal private key did not need to be copied to EC2.

### Research storage

The S3 research bucket has:

- a generated name beginning with `quant-research-platform-<environment>-data-`;
- versioning enabled;
- SSE-S3 encryption using `AES256`;
- all S3 public-access-block settings enabled; and
- `force_destroy = true` so a deliberate teardown can delete object versions and delete markers.

`force_destroy` is appropriate for this disposable POC but should be reconsidered for production or any environment containing research that must be retained.

## ParallelCluster and Slurm

Terraform installs the AWS ParallelCluster API through the `aws-tf/parallelcluster/aws` module and then manages the cluster with `aws-parallelcluster_cluster`.

The checked-in cluster configuration uses:

| Component | Configuration |
|---|---|
| ParallelCluster API | `3.15.1` |
| Operating system | Ubuntu 24.04 |
| Scheduler | Slurm |
| Head node | `t3.small`, On-Demand |
| Queue/partition | `spot` |
| Compute type | `t3.small`, Spot |
| Compute range | `MinCount = 0`, `MaxCount = 2` |
| Compute networking | Public subnet, public IP enabled |

With zero minimum workers, the normal lifecycle is:

```text
sbatch
  -> job waits for capacity
  -> ParallelCluster launches a Spot instance
  -> Ubuntu boots and slurmd registers
  -> job runs
  -> node remains warm for the idle timeout
  -> idle Spot instance is terminated
```

The experiment observed `ResumeTimeout = 2100`, `SuspendTime = 600`, and `SuspendTimeout = 120` seconds. These are generated/runtime Slurm settings observed on the deployed cluster, not explicitly declared in the checked-in Terraform.

Shared `/home` made the repository, virtual environment, Slurm logs, and scripts visible from both the head and compute nodes. That was convenient for a POC; a production platform should select and size its shared filesystem deliberately.

## Data pipeline

All Python entry points require `RESEARCH_DATA_BUCKET` to be present in the environment before the module is imported.

### 1. Ingestion

`src.ingestion.ingest` downloads unadjusted daily market data from `yfinance` for:

```text
AAPL, MSFT, NVDA, AMZN, GOOGL
```

The configured interval is `2020-01-01` up to, but not including, `2026-01-01`. For each symbol, the script retains date, OHLC prices, and volume, then writes:

```text
raw/equities/<SYMBOL>.csv
```

### 2. Normalization and validation

`src.normalization.normalize` converts source column names to:

```text
date, symbol, open, high, low, close, volume
```

It validates that:

- the dataset is not empty;
- dates and symbols are not null;
- `(date, symbol)` rows are unique;
- OHLC prices are greater than zero; and
- volume is non-negative.

Validated data is written to:

```text
normalized/equities/<SYMBOL>.csv
```

### 3. Partitioning

`src.partitioning.partition` reads normalized CSV, derives the calendar year, and writes one PyArrow Parquet object per symbol and year:

```text
curated/equities/symbol=<SYMBOL>/year=<YEAR>/data.parquet
```

This layout supports selective reads and gives the backtest independent partitions to discover under each symbol prefix.

### 4. Manifest generation

`src.orchestration.generate_manifest` creates a UUID run ID and the Cartesian product of:

- 5 symbols;
- fast windows: `5, 10, 15, 20, 25`; and
- slow windows: `30, 40, 50, 60, 70`.

That produces `5 x 5 x 5 = 125` experiment definitions, each with a stable numeric `job_id`, stored as:

```text
manifests/<RUN_ID>.json
```

The generator creates the manifest only. A checked-in Slurm script that consumes this 125-job manifest is not currently present in the repository.

## Backtest

`src.backtest.backtest` discovers all Parquet objects for one symbol, concatenates and date-sorts them, and runs a long-only moving-average crossover strategy:

```text
position = 1 when fast moving average > slow moving average
position = 0 otherwise
```

The position is shifted by one row before it is multiplied by the next market return, avoiding same-row look-ahead in signal execution. The fast window must be smaller than the slow window.

Each result includes:

- symbol and window parameters;
- compounded strategy return;
- buy-and-hold return;
- number of position changes (`trades`);
- rows processed; and
- data-load, compute, and total elapsed seconds.

The CLI is:

```bash
python -m src.backtest.backtest \
  --symbol AAPL \
  --fast-window 20 \
  --slow-window 50 \
  --run-id example-run
```

If `--run-id` is omitted, the script generates a UUID. Results are written to:

```text
results/<RUN_ID>/<SYMBOL>-<FAST>-<SLOW>.json
```

## Checkpoint and restart workflow

`src.orchestration.resilient_worker` is a deliberately simple workload for testing recovery rather than a real backtest. It divides a task into chunks, sleeps to simulate expensive work, and writes a checkpoint after every completed chunk:

```text
checkpoints/<RUN_ID>/task-<TASK_ID>.json
```

Each checkpoint records the run ID, task ID, last completed chunk, total chunks, status, hostname, Slurm job ID, Slurm restart count, and UTC update time.

On startup, the worker:

1. looks for the task checkpoint in S3;
2. starts at chunk 1 if none exists;
3. otherwise resumes at `completed_chunk + 1`; and
4. writes a final `SUCCEEDED` result after all chunks finish.

Final results use:

```text
results/<RUN_ID>/task-<TASK_ID>.json
```

The checked-in `slurm/jobs/resilience_test.sh` submits eight tasks with a maximum concurrency of four:

```bash
#SBATCH --array=0-7%4
#SBATCH --partition=spot
#SBATCH --cpus-per-task=1
#SBATCH --time=00:30:00
#SBATCH --requeue
```

Each task runs 20 chunks of 30 seconds. The four-task concurrency matches the aggregate four vCPUs exposed by two `t3.small` workers.

The job script currently contains the POC bucket name directly. Change that value, or refactor the script to receive it through deployment configuration, before recreating the environment.

## Resilience experiments

The experiments demonstrated that capacity replacement, job requeue, and application checkpointing solve different problems.

### Controlled Slurm `DOWN`: 8/8 results

The test was repeated by marking an active node down through Slurm:

```bash
sudo "$(command -v scontrol)" update \
  NodeName=spot-dy-compute-2 \
  State=DOWN \
  Reason="Controlled resilience test"
```

Observed outcome:

- Slurm recognized the node transition and requeued affected work;
- ParallelCluster supplied replacement capacity;
- restarted tasks reported `SLURM_RESTART_COUNT=1`;
- the Python worker read the last S3 checkpoint and resumed at the next chunk; and
- all eight final results were produced.

This was a successful controlled recovery test, but it was not a complete simulation of every native Spot interruption path. AWS Fault Injection Service and a managed Spot interruption simulation were unavailable for the account used during the POC.

### Direct EC2 termination: 6/8 results

While the eight-task array was running across two workers, one active EC2 instance was terminated directly.

Observed outcome:

- the worker disappeared abruptly;
- two tasks already running on it ended without final result objects;
- jobs scheduled after the node became unreachable were requeued;
- ParallelCluster created replacement capacity; and
- six of eight expected results were ultimately present.

This showed that `#SBATCH --requeue` makes work eligible for requeue but does not guarantee that every abrupt termination path will automatically restart already-running tasks exactly as intended.

## Setup and deployment

### Prerequisites

- Terraform `>= 1.10.0`
- AWS CLI credentials with permission to create the declared resources
- an existing Terraform-state S3 bucket matching `infrastructure/backend.tf`, or an edited backend configuration
- an SSH public key at `~/.ssh/id_ed25519.pub`, or an updated key path
- Python 3 and Git

### 1. Configure Terraform

```bash
cd infrastructure
cp terraform.tfvars.example terraform.tfvars
```

Replace `admin_cidr` with the current administrator public IP as a `/32`. Treat the example value as a placeholder and do not blindly deploy it.

If a named AWS profile is used, expose it to both Terraform providers:

```bash
export AWS_PROFILE=<profile-name>
export AWS_REGION=ap-southeast-1
aws sts get-caller-identity
```

### 2. Provision infrastructure

```bash
terraform init
terraform fmt -check
terraform validate
terraform plan
terraform apply
```

Review the plan before applying. The ParallelCluster API module creates a supporting CloudFormation stack; the cluster itself is managed through the ParallelCluster Terraform provider.

Useful outputs are:

```bash
terraform output research_data_bucket
terraform output parallelcluster_name
terraform output parallelcluster_status
```

### 3. Prepare the Python environment

The POC cloned this repository under `/home/ubuntu/quant-research-platform` on the head node and created the virtual environment in shared `/home`:

```bash
cd /home/ubuntu/quant-research-platform
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt

export RESEARCH_DATA_BUCKET="$(cd infrastructure && terraform output -raw research_data_bucket)"
```

Ubuntu may require the matching `python3-venv` package before creating the environment. For a reproducible production deployment, bake system and Python dependencies into an image or install them through versioned ParallelCluster custom actions rather than configuring the node manually.

### 4. Run the data workflow

```bash
python -m src.ingestion.ingest
python -m src.normalization.normalize
python -m src.partitioning.partition
python -m src.orchestration.generate_manifest
```

Then run individual backtests with `src.backtest.backtest`, or submit the resilience workload from the head node:

```bash
sbatch slurm/jobs/resilience_test.sh
squeue
sinfo
```

Update the bucket setting in `resilience_test.sh` before submitting it to a recreated environment.

## Cleanup

The completed POC was intentionally removed. Before destroying a recreated deployment:

1. Confirm no important Slurm jobs are active.
2. Decide whether results or source data must be retained outside the managed research bucket.
3. Review `terraform plan -destroy` carefully.
4. Run `terraform destroy` using the same AWS profile and region.
5. Verify that project EC2 instances, EBS volumes, ParallelCluster resources, VPC resources, and project CloudFormation stacks are gone.

The final teardown destroyed 21 Terraform-managed resources. A regional AWS-managed ParallelCluster support bucket named like `parallelcluster-<id>-v1-do-not-delete` remained. That bucket belongs to the installed ParallelCluster API lifecycle and should not be removed casually, especially if other clusters use it.

Because the research bucket is versioned and has `force_destroy = true`, Terraform can delete its object versions and delete markers during teardown. This is destructive and cannot be used as a data-retention strategy.

## Current limitations

- `src/reconciliation/reconcile.py` is empty; manifest-to-result reconciliation is a planned capability, not an implemented one.
- The repository does not contain a Slurm script that maps the generated 125-job manifest to a job array.
- The resilience Slurm script hardcodes the original POC bucket name.
- `RESEARCH_DATA_BUCKET` is read at import time, so even CLI help fails if the variable is absent.
- The five-symbol list is duplicated across modules rather than consistently imported from one configuration source.
- There are no automated tests or CI/CD checks.
- Runtime packages and the virtual environment were prepared manually on shared `/home`.
- Both head and compute nodes use a public subnet and public IPs.
- The head node is a single control-plane failure domain; head-node recovery was not tested.
- The POC uses burstable `t3.small` instances, not compute-optimized production hardware.
- Spot capacity is restricted to one instance type and subnet, reducing capacity-pool diversity.
- The backtest loads all Parquet partitions for a symbol into memory and does not paginate S3 listings beyond the first `list_objects_v2` response.
- The strategy ignores transaction costs, slippage, dividends, survivorship bias, and broader portfolio/risk constraints.
- Checkpoints overwrite one JSON object per task; production checkpointing may require immutable versions, integrity checks, input/code versioning, retention, and bounded retry policy.
- Direct EC2 termination and controlled Slurm `DOWN` do not fully validate native Spot interruption notices or repeated interruption behavior.
- Centralized logging, monitoring, alerts, cost reporting, and run-level observability are not implemented.

## Production evolution

A production design would likely add:

- private compute subnets and tighter egress controls;
- diversified Spot instance types/capacity pools and an On-Demand fallback policy;
- a versioned custom AMI or ParallelCluster custom actions;
- an explicitly selected shared filesystem such as EFS or an FSx service, based on workload I/O;
- application-aware checkpoint cadence and atomic checkpoint publishing;
- manifest reconciliation and targeted retry tooling;
- source-data, code-commit, image, dependency, and parameter lineage in every run;
- centralized Slurm, ParallelCluster, application, and cost telemetry;
- head-node backup/recovery procedures; and
- automated tests and deployment pipelines.