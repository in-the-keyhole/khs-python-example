# GCP + IaC starter — bridging from AWS

A working Terraform module that provisions a small slice of typical GCP
infra: a GCS bucket, a Pub/Sub topic + subscription, and a service account
with Workload Identity binding for use from a GKE pod.

This is **reference code**, not meant to `apply` against a real project
without changes. Read it to see the patterns; copy bits when you need them.

## The 10,000-foot view: AWS → GCP

| Concept                | AWS                        | GCP                                            |
| ---------------------- | -------------------------- | ---------------------------------------------- |
| Account boundary       | AWS Account                | **Project** (the unit of billing, IAM, quotas) |
| Org boundary           | AWS Organization           | Organization → Folders → Projects              |
| IAM model              | Policies attached to users/roles/resources | **Bindings**: `(resource, role, principal)` triples |
| Compute (containers)   | EKS / ECS                  | **GKE** (Autopilot or Standard) / Cloud Run    |
| Object storage         | S3                         | **GCS** (`gs://bucket/path`)                   |
| Pub/sub messaging      | SNS + SQS                  | **Pub/Sub** (one service, topic + subscription) |
| Managed warehouse      | Redshift                   | **BigQuery** (serverless, query-priced)        |
| Secrets                | Secrets Manager            | Secret Manager                                 |
| Workload-bound creds   | IRSA (IAM Roles for Service Accounts) | **Workload Identity** (KSA ↔ GSA binding) |
| Managed Airflow        | MWAA                       | Cloud Composer                                 |

## IaC tooling — pick one mental model

| Tool                          | Language          | Notes                                          |
| ----------------------------- | ----------------- | ---------------------------------------------- |
| **Terraform**                 | HCL               | Cloud-agnostic standard. Examples here use it. |
| **OpenTofu**                  | HCL               | Drop-in fork of Terraform; same `.tf` files.   |
| **Pulumi**                    | TS / Python / Go  | Real programming language, same provider APIs. Great fit for Bob if your team chose it. |
| Cloud Deployment Manager      | YAML/Jinja        | GCP-native, rarely used in new projects.       |
| `gcloud` CLI scripting        | shell             | Imperative; fine for ops, not infra-as-code.   |

Same `.tf` files here work with either Terraform or OpenTofu. Pulumi would
express the same resources as TypeScript / Python objects with one-to-one
mapping to the resource types.

## Read order

1. [main.tf](main.tf) — the whole stack in one annotated file.
2. [terraform.tfvars.example](terraform.tfvars.example) — copy to
   `terraform.tfvars` and fill in your project id / region.

## How a Terraform cycle works

```bash
# One-time per machine: install Terraform
brew install terraform

# One-time per project: auth gcloud as yourself
gcloud auth application-default login

# In this directory:
cp terraform.tfvars.example terraform.tfvars
# edit terraform.tfvars with your real project_id

terraform init     # downloads the google provider plugin into .terraform/
terraform plan     # shows what it WOULD create — no changes yet
terraform apply    # actually creates resources after you type "yes"
terraform destroy  # tears them down
```

## `gcloud` CLI cheat sheet

```bash
# Auth
gcloud auth login                                  # interactive, browser
gcloud auth application-default login              # for SDKs / Terraform
gcloud config set project my-project-id
gcloud config set compute/region us-central1

# Inspect
gcloud projects list
gcloud iam service-accounts list
gcloud storage ls                                   # list buckets
gcloud pubsub topics list

# GKE
gcloud container clusters get-credentials my-cluster --region us-central1
# (writes a kubeconfig context so `kubectl` works against the cluster)

# Secrets
gcloud secrets list
gcloud secrets versions access latest --secret=my-secret
```

## Two things that bite AWS people on GCP

1. **APIs are off by default.** Before you can use BigQuery, Pub/Sub, GKE,
   etc., you must enable the API on the project (`gcloud services enable
   bigquery.googleapis.com`). Terraform can do this for you — see the
   `google_project_service` resource in `main.tf`.
2. **IAM bindings, not policies.** AWS lets you attach a JSON policy with N
   statements. GCP IAM is a flat list of `(resource, role, principal)`
   bindings. You don't write policy documents — you grant roles. Custom
   roles exist but predefined roles cover ~95% of needs.

## Where state lives

Don't commit `terraform.tfstate` — it contains resource IDs and sometimes
secrets. In production, use a **remote backend** so state is shared:

```hcl
terraform {
  backend "gcs" {
    bucket = "keyhole-terraform-state"
    prefix = "khs-python-example"
  }
}
```

AWS analogue: an S3 backend with a DynamoDB lock table. GCS does locking
natively, so no separate lock resource needed.
