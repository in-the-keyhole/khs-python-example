"""
Classic-API Airflow DAG. This is the style you'll see in 80% of existing
codebases. Read it top-to-bottom — annotations call out what differs from
a Node/Express mental model.

This file is meant to be deployed to an Airflow environment (Cloud Composer
or self-hosted on GKE). `apache-airflow` is installed as a dev dep so the
imports resolve and the file is covered by ruff/lint — but `pytest` and
`uvicorn` ignore it. DAG files are deployment artifacts, not app runtime code.
"""

from datetime import datetime, timedelta

from airflow.providers.standard.operators.bash import BashOperator
from airflow.providers.standard.operators.python import PythonOperator

from airflow import DAG

# ---------- task callables ----------
# Plain Python functions. Airflow wraps them in a task lifecycle (logging,
# retries, XCom serialization) when run via PythonOperator.


def extract(**context) -> list[dict]:
    """
    Pretend to pull from an API. The return value is automatically pushed
    to XCom (Airflow's metadata DB) under this task's id, so downstream
    tasks can read it.

    `**context` gives access to runtime info: execution date, task instance,
    DAG run id, etc. Always include it even if you don't use it — Airflow
    passes a dict of kwargs and a strict signature would error.
    """
    print(f"Extracting for logical date {context['logical_date']}")
    return [
        {"id": 1, "name": "widget", "price": 9.99},
        {"id": 2, "name": "gadget", "price": 14.50},
    ]


def transform(**context) -> list[dict]:
    """
    Read upstream output from XCom. `ti` = TaskInstance. `xcom_pull` with
    a task_id grabs whatever that task returned.
    """
    ti = context["ti"]
    rows = ti.xcom_pull(task_ids="extract")
    return [{**row, "price_with_tax": round(row["price"] * 1.08, 2)} for row in rows]


def load(**context) -> None:
    rows = context["ti"].xcom_pull(task_ids="transform")
    print(f"Loading {len(rows)} rows: {rows}")
    # In production: write to BigQuery, Postgres, GCS, etc.


# ---------- DAG definition ----------
# `default_args` apply to every task unless overridden. Common pattern.

default_args = {
    "owner": "data-eng",
    "retries": 3,
    "retry_delay": timedelta(minutes=2),
    "email_on_failure": False,
}

with DAG(
    dag_id="etl_basic",  # unique across the Airflow instance
    description="Toy ETL: extract → transform → load with XCom hand-off",
    start_date=datetime(2026, 5, 1),  # first logical date Airflow will schedule
    schedule="@daily",  # cron string, preset, or timetable
    catchup=False,  # don't backfill missed runs on first deploy
    max_active_runs=1,  # never run two of this DAG concurrently
    default_args=default_args,
    tags=["example", "etl"],
) as dag:
    extract_task = PythonOperator(
        task_id="extract",
        python_callable=extract,
    )

    transform_task = PythonOperator(
        task_id="transform",
        python_callable=transform,
    )

    load_task = PythonOperator(
        task_id="load",
        python_callable=load,
    )

    # The bitshift operator is overloaded to declare task dependencies.
    # Reads left-to-right as the data flow.
    extract_task >> transform_task >> load_task

    # Common alternatives:
    #   extract_task.set_downstream(transform_task)             # equivalent
    #   [t1, t2] >> t3                                          # fan-in
    #   t1 >> [t2, t3]                                          # fan-out

    # BashOperator example — runs an arbitrary shell command as a task.
    # Useful for invoking dbt, kicking off gcloud commands, calling other CLIs.
    notify = BashOperator(
        task_id="notify",
        # `{{ ds }}` is a Jinja-templated date macro provided by Airflow.
        bash_command='echo "ETL finished for {{ ds }}"',
    )

    load_task >> notify
