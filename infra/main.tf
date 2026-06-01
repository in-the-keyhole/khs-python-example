# Terraform module: GCP starter slice.
#
# Provisions:
#   - APIs enabled on the project (you can't use a service until its API is on)
#   - A GCS bucket with versioning + lifecycle
#   - A Pub/Sub topic + pull subscription
#   - A Google service account for an Airflow worker pod
#   - A Workload Identity binding that lets a Kubernetes ServiceAccount
#     in GKE impersonate the Google service account — no key files needed
#
# This is a learning artifact, not a production module. A real module would
# split into providers.tf / variables.tf / outputs.tf, add lifecycle blocks,
# tag everything, and parameterize far more.

# ---------- providers ----------

terraform {
  required_version = ">= 1.6"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # Remote state — uncomment and create the bucket once before `terraform init`.
  # backend "gcs" {
  #   bucket = "keyhole-terraform-state"
  #   prefix = "khs-python-example"
  # }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# ---------- variables ----------
# Like environment / config inputs. Values come from terraform.tfvars,
# -var CLI flags, or TF_VAR_ env vars.

variable "project_id" {
  description = "GCP project to deploy into."
  type        = string
}

variable "region" {
  description = "Default GCP region."
  type        = string
  default     = "us-central1"
}

variable "env" {
  description = "dev | staging | prod. Used for naming + tagging."
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.env)
    error_message = "env must be one of dev, staging, prod."
  }
}

variable "gke_namespace" {
  description = "Kubernetes namespace the Airflow workers run in."
  type        = string
  default     = "airflow"
}

variable "gke_service_account_name" {
  description = "Name of the KSA Airflow workers use."
  type        = string
  default     = "airflow-worker"
}

# Local values — computed once, referenced many times.
locals {
  name_prefix = "khs-${var.env}"
  labels = {
    env       = var.env
    owner     = "data-eng"
    managed_by = "terraform"
  }
}

# ---------- enable APIs ----------
# Each Google service is gated by its API. Enable them before use.

resource "google_project_service" "apis" {
  for_each = toset([
    "storage.googleapis.com",
    "pubsub.googleapis.com",
    "iam.googleapis.com",
    "bigquery.googleapis.com",
    "sqladmin.googleapis.com",
    "secretmanager.googleapis.com",
  ])
  service            = each.value
  disable_on_destroy = false
}

# ---------- GCS bucket ----------

resource "google_storage_bucket" "landing" {
  name                        = "${local.name_prefix}-landing"
  location                    = var.region
  uniform_bucket_level_access = true                # disable per-object ACLs (S3 ACL equivalent — turn them off)
  force_destroy               = var.env != "prod"   # safety: never force-destroy prod data

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition { age = 30 }                          # delete noncurrent versions after 30 days
    action    { type = "Delete" }
  }

  labels     = local.labels
  depends_on = [google_project_service.apis]
}

# ---------- Pub/Sub ----------

resource "google_pubsub_topic" "events" {
  name       = "${local.name_prefix}-events"
  labels     = local.labels
  depends_on = [google_project_service.apis]
}

resource "google_pubsub_subscription" "events_worker" {
  name  = "${local.name_prefix}-events-worker"
  topic = google_pubsub_topic.events.name

  ack_deadline_seconds = 30
  retain_acked_messages = false
  message_retention_duration = "604800s"            # 7 days

  expiration_policy {
    ttl = ""                                        # never expire (default is 31 days)
  }

  labels = local.labels
}

# ---------- Service Account + Workload Identity ----------

resource "google_service_account" "airflow_worker" {
  account_id   = "${local.name_prefix}-airflow"
  display_name = "Airflow worker (${var.env})"
}

# Grant the SA permission to read/write the landing bucket and publish to
# the topic. AWS analogue: attaching a policy to a role.
resource "google_storage_bucket_iam_member" "airflow_bucket_rw" {
  bucket = google_storage_bucket.landing.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.airflow_worker.email}"
}

resource "google_pubsub_topic_iam_member" "airflow_topic_publisher" {
  topic  = google_pubsub_topic.events.name
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${google_service_account.airflow_worker.email}"
}

# Workload Identity binding: lets the Kubernetes ServiceAccount impersonate
# this GCP service account. Inside the pod, the Google SDKs see credentials
# automatically — no key files mounted, no secrets to rotate.
#
# After applying, annotate the KSA in your cluster:
#   kubectl annotate serviceaccount -n airflow airflow-worker \
#     iam.gke.io/gcp-service-account=khs-dev-airflow@<project>.iam.gserviceaccount.com
resource "google_service_account_iam_member" "workload_identity" {
  service_account_id = google_service_account.airflow_worker.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[${var.gke_namespace}/${var.gke_service_account_name}]"
}

# ---------- outputs ----------
# Like return values — visible after `terraform apply` and consumable by
# other modules / CI / docs.

output "bucket_name" {
  value = google_storage_bucket.landing.name
}

output "topic_name" {
  value = google_pubsub_topic.events.name
}

output "airflow_service_account_email" {
  value = google_service_account.airflow_worker.email
}

output "workload_identity_annotation" {
  description = "Run this kubectl command to bind your KSA after apply."
  value = format(
    "kubectl annotate serviceaccount -n %s %s iam.gke.io/gcp-service-account=%s --overwrite",
    var.gke_namespace,
    var.gke_service_account_name,
    google_service_account.airflow_worker.email,
  )
}
