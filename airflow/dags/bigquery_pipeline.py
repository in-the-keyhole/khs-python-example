"""
TaskFlow-API DAG with real GCP operators. This is the style to prefer in
new code — function calls express the graph, return values become XCom
automatically, no manual `>>` wiring.

Pattern: wait for a file to land in GCS → load it into BigQuery → run a
transform query → export the result back to GCS.

Auth: on GKE / Composer the worker pod's service account has the BigQuery
and GCS permissions it needs (via Workload Identity binding). No key files,
no credentials in code.
"""

from datetime import datetime, timedelta

from airflow.decorators import dag, task
from airflow.providers.google.cloud.operators.bigquery import BigQueryInsertJobOperator
from airflow.providers.google.cloud.sensors.gcs import GCSObjectExistenceSensor
from airflow.providers.google.cloud.transfers.gcs_to_bigquery import GCSToBigQueryOperator

# Real codebases pull these from Airflow Variables or env vars, not hardcoded.
GCP_PROJECT = "keyhole-example-project"
BQ_DATASET = "analytics"
GCS_BUCKET = "keyhole-example-landing"


@dag(
    dag_id="bigquery_pipeline",
    description="Daily: wait for CSV → load to BQ → aggregate → export",
    start_date=datetime(2026, 5, 1),
    schedule="0 6 * * *",  # 06:00 UTC daily
    catchup=False,
    default_args={
        "retries": 3,
        "retry_delay": timedelta(minutes=5),
    },
    tags=["example", "bigquery"],
)
def bigquery_pipeline():
    """
    Each function decorated with @task becomes an Airflow task. Calling
    them inside this function builds the graph — Airflow inspects the
    call chain to figure out dependencies. No `>>` needed.
    """

    # ---------- Sensor: poll GCS until today's file lands ----------
    # `{{ ds }}` = the DAG run's logical date (YYYY-MM-DD), Jinja-templated.
    # Sensors block the task slot — for long waits, use `mode="reschedule"`
    # to free the worker between polls.
    wait_for_file = GCSObjectExistenceSensor(
        task_id="wait_for_file",
        bucket=GCS_BUCKET,
        object="incoming/sales-{{ ds }}.csv",
        timeout=60 * 60,  # give up after 1 hour
        poke_interval=60,  # check every 60s
        mode="reschedule",
    )

    # ---------- Operator: load CSV to a raw BQ table ----------
    load_raw = GCSToBigQueryOperator(
        task_id="load_raw",
        bucket=GCS_BUCKET,
        source_objects=["incoming/sales-{{ ds }}.csv"],
        destination_project_dataset_table=(
            f"{GCP_PROJECT}.{BQ_DATASET}.sales_raw${{{{ ds_nodash }}}}"
        ),
        source_format="CSV",
        skip_leading_rows=1,
        write_disposition="WRITE_TRUNCATE",  # replace today's partition
        autodetect=True,
    )

    # ---------- TaskFlow task: compute config, hand to next task as XCom ----------
    @task
    def make_query_params(execution_ds: str) -> dict:
        """
        A plain Python function exposed as a task. Return value is XCom'd
        automatically; downstream tasks receive it as a parameter.
        """
        return {
            "ds": execution_ds,
            "source": f"{GCP_PROJECT}.{BQ_DATASET}.sales_raw",
            "dest": f"{GCP_PROJECT}.{BQ_DATASET}.sales_daily",
        }

    params = make_query_params("{{ ds }}")

    # ---------- Operator: run a SQL aggregation in BigQuery ----------
    aggregate = BigQueryInsertJobOperator(
        task_id="aggregate",
        configuration={
            "query": {
                "query": (
                    "INSERT INTO `{{ ti.xcom_pull(task_ids='make_query_params')['dest'] }}` "
                    "SELECT '{{ ds }}' AS day, region, SUM(amount) AS total "
                    "FROM `{{ ti.xcom_pull(task_ids='make_query_params')['source'] }}` "
                    "WHERE _PARTITIONDATE = '{{ ds }}' "
                    "GROUP BY region"
                ),
                "useLegacySql": False,
            }
        },
    )

    # ---------- Wire the graph ----------
    # TaskFlow infers dependencies from function calls (`params` was returned
    # by make_query_params, so aggregate depends on it). For traditional
    # operators we still use `>>`.
    wait_for_file >> load_raw >> params >> aggregate


# This trailing call is what registers the DAG with Airflow. Easy to forget.
bigquery_pipeline()
