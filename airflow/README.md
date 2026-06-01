# Airflow on GKE / Cloud Composer — the Python you'll write at work

FastAPI was *web-app* Python. Airflow is *workflow-orchestration* Python.
Same language, totally different mental model.

## What Airflow is, in one sentence

A scheduler + executor + UI that runs **directed graphs of Python tasks**
on a recurring schedule, with retries, backfills, and rich operator
integrations for cloud services.

## Node mental anchors

| Airflow concept                 | Closest Node analogue                       |
| ------------------------------- | ------------------------------------------- |
| DAG                             | A Temporal workflow / BullMQ job graph      |
| Operator                        | A reusable job class (DB query, HTTP call)  |
| TaskFlow `@task`                | The async/await version of operators        |
| XCom                            | Step return values, but stored in metadata DB |
| Sensor                          | A poll loop with backoff, but declarative   |
| Scheduler                       | `node-cron` + a state machine               |
| Hook                            | A typed cloud-SDK client wrapper            |
| Pool                            | A concurrency limiter (like p-limit)        |
| Connection                      | A named credential (like an env var, but in the DB and UI-managed) |

## The two API styles you'll see in real code

### Classic API ([dags/etl_basic.py](dags/etl_basic.py))

```python
with DAG("etl", schedule="@daily", ...) as dag:
    a = PythonOperator(task_id="a", python_callable=fn_a)
    b = PythonOperator(task_id="b", python_callable=fn_b)
    a >> b   # `>>` declares "a runs before b"
```

Verbose but explicit. Older codebases use it heavily.

### TaskFlow API ([dags/bigquery_pipeline.py](dags/bigquery_pipeline.py))

```python
@dag(schedule="@daily", ...)
def pipeline():
    @task
    def extract() -> dict: ...
    @task
    def load(rows: dict) -> None: ...
    load(extract())   # graph inferred from function calls
pipeline()
```

Available since Airflow 2.0. Reads almost like normal Python — return values
become XCom automatically, dependencies are inferred from function calls.
**Prefer this in new code.**

## How DAGs ship to production

You don't run Airflow locally for this project. The path is:

1. Write a DAG file (just a Python module that defines `dag = DAG(...)` or
   uses `@dag`).
2. Commit it to the repo your team's Airflow watches — usually synced to a
   GCS bucket (Cloud Composer does this with a `dags/` folder on GCS).
3. Within ~30s the scheduler picks it up and shows it in the UI.

**Cloud Composer** is GCP's managed Airflow on GKE. It's expensive (~$300+/mo
for the smallest env) but removes the operational burden of running Airflow
yourself. AWS analogue: MWAA.

## Local development options

You don't need any of these to *read* the example DAGs in `dags/`. Pick one
only if you want IDE autocompletion or to run a DAG without deploying:

| Goal                          | How                                              |
| ----------------------------- | ------------------------------------------------ |
| IDE resolves `from airflow import …` | **already done** — `apache-airflow` + Google provider are dev deps |
| Just validate DAG syntax      | `uv run python airflow/dags/etl_basic.py` — if it imports without error, the scheduler will parse it |
| Run a DAG end-to-end locally  | `uv run airflow standalone` (SQLite + LocalExecutor — heavy startup, slow) |
| Production-faithful local env | `astro dev start` (the Astronomer CLI runs Airflow in Docker) |

## GCP-specific operators you'll reach for constantly

- `BigQueryInsertJobOperator` — run a query / load / extract / copy job
- `GCSObjectExistenceSensor` — wait for a file to land
- `GCSToBigQueryOperator` — bulk load CSV/JSON/Parquet from GCS to BQ
- `BigQueryToGCSOperator` — export query results to GCS
- `PubSubPullSensor` — wait for messages
- `DataflowStartFlexTemplateOperator` — kick off a Dataflow job
- `KubernetesPodOperator` — run an arbitrary container as a task (your escape hatch when no operator fits)

Auth happens via **Workload Identity** — the GKE service account that Airflow
runs as is bound to a GCP service account, so the operators authenticate
transparently with no key files.

## Read order

1. [dags/etl_basic.py](dags/etl_basic.py) — classic API, the patterns everywhere.
2. [dags/bigquery_pipeline.py](dags/bigquery_pipeline.py) — TaskFlow API + real GCP operators.

Both files have heavy inline comments calling out the bits that aren't
obvious from a Node perspective.
