# Cloud SQL Postgres for the e-commerce OLTP "orders" database.
#
# This is the source of truth that the Airflow DAG `postgres_to_bq_orders`
# extracts from each night. It also backs the FastAPI service in local dev
# (via docker compose) and prod (via this Cloud SQL instance).
#
# Layout:
#   - One google_sql_database_instance (the server)
#   - One google_sql_database         (the logical DB named "orders")
#   - One google_sql_user             (the app user, password from random_password)
#   - Secret Manager entry storing the generated password
#   - IAM: roles/cloudsql.client granted to the airflow_worker SA so the
#     Airflow PostgresHook can connect via the Cloud SQL Auth Proxy.

# ---------- random password ----------
# Generated once, stored in Secret Manager, and fed straight into the SQL user.
# No human ever sees or types it.
resource "random_password" "orders_pg" {
  length  = 24
  special = true
}

# ---------- the instance ----------
resource "google_sql_database_instance" "orders_pg" {
  name             = "${local.name_prefix}-orders-pg"
  database_version = "POSTGRES_16"
  region           = var.region

  # Protect prod from `terraform destroy`. Dev/staging stay disposable.
  deletion_protection = var.env == "prod"

  settings {
    tier              = "db-f1-micro"
    availability_type = "ZONAL"
    disk_size         = 10
    disk_type         = "PD_SSD"

    ip_configuration {
      # Public IP is enabled here for dev convenience so you can connect from
      # your laptop via the Cloud SQL Auth Proxy without setting up VPC peering.
      #
      # PROD NOTE: flip ipv4_enabled to false and set private_network to a
      # VPC self_link, e.g.:
      #   private_network = google_compute_network.vpc.id
      # then connect from GKE pods over the private IP only.
      ipv4_enabled = true
    }

    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true
      start_time                     = "03:00"
    }

    user_labels = local.labels
  }

  depends_on = [google_project_service.apis]
}

# ---------- the "orders" database ----------
resource "google_sql_database" "orders" {
  name     = "orders"
  instance = google_sql_database_instance.orders_pg.name
}

# ---------- the app user ----------
resource "google_sql_user" "app" {
  name     = "app"
  instance = google_sql_database_instance.orders_pg.name
  password = random_password.orders_pg.result
}

# ---------- store the password in Secret Manager ----------
# Apps fetch it at runtime via `gcloud secrets versions access latest --secret=...`
# or the Secret Manager client library. Never committed, never logged.
resource "google_secret_manager_secret" "orders_pg_password" {
  secret_id = "${local.name_prefix}-orders-pg-password"

  replication {
    auto {}
  }

  labels     = local.labels
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "orders_pg_password" {
  secret      = google_secret_manager_secret.orders_pg_password.id
  secret_data = random_password.orders_pg.result
}

# ---------- IAM: let the Airflow worker connect ----------
# roles/cloudsql.client lets the SA open connections through the Cloud SQL
# Auth Proxy. It does NOT grant any SQL-level privileges — those come from
# the Postgres GRANTs against the "app" user.
resource "google_project_iam_member" "airflow_cloudsql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.airflow_worker.email}"
}

# ---------- outputs ----------
output "instance_connection_name" {
  description = "Pass this to the Cloud SQL Auth Proxy (project:region:instance)."
  value       = google_sql_database_instance.orders_pg.connection_name
}

output "password_secret_id" {
  description = "Secret Manager secret holding the app user's password."
  value       = google_secret_manager_secret.orders_pg_password.secret_id
}
