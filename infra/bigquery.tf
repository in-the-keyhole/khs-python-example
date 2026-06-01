# BigQuery warehouse for orders analytics.
#
# Two tables:
#   - analytics.orders_raw   — daily snapshot loaded by the Airflow DAG.
#                              Partitioned by DATE(ingested_at), clustered by region.
#                              The DAG deletes the day's partition before insert,
#                              so reruns are idempotent.
#   - analytics.sales_daily  — aggregate computed from orders_raw, partitioned by day,
#                              clustered by region. One row per (day, region).
#
# Schema decisions:
#   - `id` and `customer_id` use INT64 to match Postgres BIGINT. BigQuery's
#     INT64 holds ±9.2e18 which is the same range as Postgres BIGINT, so no
#     need for BIGNUMERIC here.
#   - `total_cents` uses INT64 — currency stored as integer cents avoids float
#     rounding bugs. The aggregate dollarizes via /100 into NUMERIC for the
#     gross_revenue column where decimals matter.
#   - `gross_revenue` is NUMERIC (BigQuery's exact decimal, 38 digits / 9 scale).

# ---------- dataset ----------
resource "google_bigquery_dataset" "analytics" {
  dataset_id = "analytics"

  # Multi-region "US" works for any us-* region (us-central1, us-east1, ...).
  # For EU regions use "EU"; for asia/other multi-regions, hardcode the matching
  # multi-region name here. Multi-region is preferred over single-region for
  # warehouse datasets — better availability, same price.
  location = "US"

  description                = "Orders analytics: raw daily snapshot + sales aggregates."
  delete_contents_on_destroy = var.env != "prod"

  labels     = local.labels
  depends_on = [google_project_service.apis]
}

# ---------- orders_raw ----------
# Mirror of the Postgres `orders` table, plus an `ingested_at` column the DAG
# writes so we know which run produced each row.
resource "google_bigquery_table" "orders_raw" {
  dataset_id = google_bigquery_dataset.analytics.dataset_id
  table_id   = "orders_raw"

  # Don't let `terraform destroy` nuke prod data.
  deletion_protection = var.env == "prod"

  description = "Raw orders snapshot, one row per Postgres order, ingested daily by the postgres_to_bq_orders DAG."

  time_partitioning {
    type  = "DAY"
    field = "ingested_at"
  }

  clustering = ["region"]

  schema = jsonencode([
    {
      name        = "id"
      type        = "INT64"
      mode        = "REQUIRED"
      description = "Postgres orders.id (BIGINT)."
    },
    {
      name        = "customer_id"
      type        = "INT64"
      mode        = "REQUIRED"
      description = "FK to customers (BIGINT in Postgres)."
    },
    {
      name        = "total_cents"
      type        = "INT64"
      mode        = "REQUIRED"
      description = "Order total in integer cents to avoid float rounding."
    },
    {
      name        = "status"
      type        = "STRING"
      mode        = "REQUIRED"
      description = "One of: pending, paid, shipped, cancelled."
    },
    {
      name        = "region"
      type        = "STRING"
      mode        = "REQUIRED"
      description = "Shipping region, e.g. us-west, us-east, eu. Cluster key."
    },
    {
      name        = "created_at"
      type        = "TIMESTAMP"
      mode        = "REQUIRED"
      description = "When the order was created in the OLTP DB."
    },
    {
      name        = "ingested_at"
      type        = "TIMESTAMP"
      mode        = "REQUIRED"
      description = "When this row was loaded into BigQuery. Partition key."
    },
  ])

  labels = local.labels
}

# ---------- sales_daily ----------
# One row per (day, region) — small, dashboard-friendly aggregate.
resource "google_bigquery_table" "sales_daily" {
  dataset_id = google_bigquery_dataset.analytics.dataset_id
  table_id   = "sales_daily"

  deletion_protection = var.env == "prod"

  description = "Per-day, per-region sales aggregate built from orders_raw."

  time_partitioning {
    type  = "DAY"
    field = "day"
  }

  clustering = ["region"]

  schema = jsonencode([
    {
      name        = "day"
      type        = "DATE"
      mode        = "REQUIRED"
      description = "Calendar day (UTC). Partition key."
    },
    {
      name        = "region"
      type        = "STRING"
      mode        = "REQUIRED"
      description = "Region. Cluster key."
    },
    {
      name        = "order_count"
      type        = "INT64"
      mode        = "REQUIRED"
      description = "Number of orders that day in this region."
    },
    {
      name        = "gross_revenue"
      type        = "NUMERIC"
      mode        = "REQUIRED"
      description = "SUM(total_cents)/100 — exact decimal dollars."
    },
  ])

  labels = local.labels
}

# ---------- IAM ----------
# Dataset-scoped editor: the Airflow worker can create/replace tables and
# read/write data inside `analytics`, but not in any other dataset.
resource "google_bigquery_dataset_iam_member" "airflow_data_editor" {
  dataset_id = google_bigquery_dataset.analytics.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.airflow_worker.email}"
}

# Project-level jobUser: required to *submit* BigQuery jobs (query, load,
# insert). dataEditor by itself isn't enough — you also need permission to
# run a job somewhere. Project-level is the standard pattern.
resource "google_project_iam_member" "airflow_bq_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.airflow_worker.email}"
}

# ---------- outputs ----------
output "dataset_id" {
  value = google_bigquery_dataset.analytics.dataset_id
}

output "orders_raw_id" {
  value = "${google_bigquery_dataset.analytics.dataset_id}.${google_bigquery_table.orders_raw.table_id}"
}

output "sales_daily_id" {
  value = "${google_bigquery_dataset.analytics.dataset_id}.${google_bigquery_table.sales_daily.table_id}"
}
