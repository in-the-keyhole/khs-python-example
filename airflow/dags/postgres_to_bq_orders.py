"""
Daily Postgres → BigQuery ETL for the e-commerce `orders` table.

Data flow (matches the project SPEC exactly):

    Postgres (OLTP)                BigQuery
    ───────────────                ────────
    public.orders   ─extract─►  analytics.orders_raw   ─aggregate─►  analytics.sales_daily

Tasks (run in order, once a day at 02:00 UTC):

    1. extract_postgres  — pull yesterday's rows from `public.orders` via the
                           PostgresHook bound to the Airflow connection
                           "postgres_oltp". Returns list[dict] → XCom.
    2. load_raw          — delete today's partition in `analytics.orders_raw`
                           (idempotent reload), tag each row with
                           ingested_at = logical_date, then insert via
                           BigQueryHook on the default Google connection.
    3. aggregate         — pure BigQueryInsertJobOperator that GROUP BYs the
                           freshly-loaded partition into `analytics.sales_daily`.

Node → Airflow bridging notes for the reader:

* An Airflow "connection id" is just a named credential the worker resolves at
  runtime (think: a row in a secrets table). Code never sees the username,
  password, or host — only the connection id string. That's why `PG_CONN_ID`
  below is a plain string like "postgres_oltp", not a URL.
* Hooks (PostgresHook, BigQueryHook) are the low-level client objects — like
  a `pg` Client or a `@google-cloud/bigquery` BigQuery instance in Node.
  Operators (BigQueryInsertJobOperator) are higher-level "do one thing as a
  task" wrappers. We use a hook when we want imperative control inside an
  @task; an operator when the whole task IS that one call.
* `{{ ds }}` in operator kwargs is a Jinja macro Airflow expands at run time
  to the run's logical date (YYYY-MM-DD). Inside @task functions we use the
  `context` dict (`context["ds"]`, `context["logical_date"]`) instead.
* Return values from @task functions auto-serialize to XCom (Airflow's
  metadata DB) — analogous to passing a value from one Lambda step to the
  next in a Step Functions state machine.
"""

from datetime import datetime, timedelta

from airflow.decorators import dag, task
from airflow.providers.google.cloud.hooks.bigquery import BigQueryHook
from airflow.providers.google.cloud.operators.bigquery import BigQueryInsertJobOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook

# ───────────────────────── Constants ─────────────────────────
# Real codebases pull these from Airflow Variables, env vars, or a config
# module. Hardcoded here to keep the example self-contained.
GCP_PROJECT = "keyhole-example-project"
BQ_DATASET = "analytics"

# Connection ids resolved from Airflow's connections table at runtime.
# The Postgres conn ("postgres_oltp") points at the OLTP `orders` DB.
# The BigQuery conn ("google_cloud_default") is the convention name the
# Google provider falls back to — on GKE/Composer it picks up the worker
# pod's service account via Workload Identity, no key file required.
PG_CONN_ID = "postgres_oltp"
BQ_CONN_ID = "google_cloud_default"

# Fully-qualified BQ table refs. Kept as module-level constants so both the
# Python hook code and the templated SQL string below stay in sync.
ORDERS_RAW_TABLE = f"{GCP_PROJECT}.{BQ_DATASET}.orders_raw"
SALES_DAILY_TABLE = f"{GCP_PROJECT}.{BQ_DATASET}.sales_daily"


@dag(
    dag_id="postgres_to_bq_orders",
    description="Daily: extract orders from Postgres → load to BQ raw → aggregate to sales_daily",
    start_date=datetime(2026, 5, 1),
    schedule="0 2 * * *",  # 02:00 UTC daily
    catchup=False,
    max_active_runs=1,
    default_args={
        "retries": 3,
        "retry_delay": timedelta(minutes=5),
    },
    tags=["example", "postgres", "bigquery", "orders"],
)
def postgres_to_bq_orders():
    """
    TaskFlow-style DAG. Each @task is a node in the graph; calling them inside
    this function builds the dependency edges (Airflow inspects the call
    chain). The pure Operator at the bottom is wired manually with `>>`.
    """

    # ────────────────────── 1. Extract from Postgres ──────────────────────
    @task
    def extract_postgres(**context) -> list[dict]:
        """
        Pull yesterday's orders out of Postgres.

        `context["ds"]` is the run's logical date as a YYYY-MM-DD string —
        same value Jinja `{{ ds }}` would render to. We parameterize the
        query with `%s` (psycopg server-side bind) rather than f-stringing
        the date in, to keep the habit of avoiding SQL injection even
        though `ds` is Airflow-controlled.

        Return type is `list[dict]` because XCom serialization prefers JSON-
        friendly shapes — raw psycopg row tuples don't round-trip cleanly,
        and a pandas DataFrame would be heavier than we need here.
        """
        ds = context["ds"]
        hook = PostgresHook(postgres_conn_id=PG_CONN_ID)

        sql = (
            "SELECT id, customer_id, total_cents, status, region, created_at "
            "FROM public.orders "
            "WHERE created_at::date = %s"
        )
        # get_records returns list[tuple]. We pair it with an explicit column
        # list so the dict keys are stable even if the SELECT order changes.
        columns = ["id", "customer_id", "total_cents", "status", "region", "created_at"]
        records = hook.get_records(sql, parameters=(ds,))

        rows = [dict(zip(columns, row, strict=True)) for row in records]

        # `created_at` comes back as a datetime — XCom JSON serializer handles
        # it, but if you ever swap to a stricter serializer you'd .isoformat()
        # it here. Leaving as-is for readability.
        print(f"Extracted {len(rows)} orders for {ds}")
        return rows

    # ────────────────────── 2. Load to BQ raw table ──────────────────────
    @task
    def load_raw(rows: list[dict], **context) -> int:
        """
        Idempotent reload of today's partition in `analytics.orders_raw`.

        Why delete-then-insert instead of WRITE_TRUNCATE on the whole table?
        Because `orders_raw` is partitioned by DATE(ingested_at) and we only
        want to replace today's slice — a backfill of 2026-05-10 must not
        wipe 2026-05-09's rows. The DELETE scopes the rewrite to one day.

        Each row is stamped with `ingested_at = logical_date` so the
        partition column has a deterministic value (re-runs land in the
        same partition). `context["logical_date"]` is a timezone-aware
        datetime; BQ's TIMESTAMP type accepts the ISO string form.
        """
        ds = context["ds"]
        logical_date = context["logical_date"]
        ingested_at_iso = logical_date.isoformat()

        hook = BigQueryHook(gcp_conn_id=BQ_CONN_ID, use_legacy_sql=False)

        # Step 2a: clear the partition. Running this DELETE in a DML job is
        # the canonical "idempotent partition reload" trick on BigQuery —
        # cheaper than a full table rewrite and safe to re-run.
        delete_sql = f"DELETE FROM `{ORDERS_RAW_TABLE}` WHERE DATE(ingested_at) = '{ds}'"
        # `run_query` returns a job id; we don't need it but we do want the
        # call to block until BQ finishes, so subsequent inserts see a clean
        # partition.
        client = hook.get_client(project_id=GCP_PROJECT)
        client.query(delete_sql).result()

        if not rows:
            # Nothing to insert — common on weekends / quiet days. Skipping
            # the insert avoids a no-op streaming call and an empty-rows
            # warning from the BQ client.
            print(f"No rows to load for {ds}; partition cleared.")
            return 0

        # Step 2b: stamp rows with ingested_at, then bulk insert. The hook's
        # `insert_all_rows` is the streaming-insert path; for higher volumes
        # a load job from GCS would be cheaper, but for the order volumes
        # we expect this is fine.
        stamped = [
            {
                **row,
                # datetimes from Postgres round-trip as iso strings for the
                # streaming insert API.
                "created_at": row["created_at"].isoformat()
                if hasattr(row["created_at"], "isoformat")
                else row["created_at"],
                "ingested_at": ingested_at_iso,
            }
            for row in rows
        ]

        hook.insert_all(
            project_id=GCP_PROJECT,
            dataset_id=BQ_DATASET,
            table_id="orders_raw",
            rows=stamped,
        )
        print(f"Loaded {len(stamped)} rows into {ORDERS_RAW_TABLE} for {ds}")
        return len(stamped)

    # ────────────────────── 3. Aggregate into sales_daily ──────────────────────
    # Pure operator (not @task): the whole job IS a single BQ query, no
    # Python glue needed. Templated `{{ ds }}` is expanded by Airflow at
    # render time, so the SQL string here can stay declarative.
    aggregate = BigQueryInsertJobOperator(
        task_id="aggregate",
        gcp_conn_id=BQ_CONN_ID,
        configuration={
            "query": {
                "query": (
                    f"INSERT INTO `{SALES_DAILY_TABLE}` (day, region, order_count, gross_revenue) "
                    # `DATE('{{ ds }}')` — `{{ ds }}` is a STRING template; cast
                    # to DATE so BigQuery accepts it for the DATE column.
                    "SELECT DATE('{{ ds }}') AS day, "
                    "region, "
                    "COUNT(*) AS order_count, "
                    # CAST to NUMERIC before dividing: INT64/INT64 returns
                    # FLOAT64 in BigQuery, which won't implicitly cast to the
                    # NUMERIC target column. Casting first preserves precision
                    # and matches the "exact decimal dollars" contract.
                    "CAST(SUM(total_cents) AS NUMERIC) / 100 AS gross_revenue "
                    f"FROM `{ORDERS_RAW_TABLE}` "
                    "WHERE DATE(ingested_at) = '{{ ds }}' "
                    "GROUP BY region"
                ),
                "useLegacySql": False,
            }
        },
    )

    # ────────────────────── Wire the graph ──────────────────────
    # TaskFlow infers the extract → load_raw edge from the function-call
    # chain (load_raw consumes the return value of extract_postgres).
    # For the operator we still use `>>`.
    rows = extract_postgres()
    loaded = load_raw(rows)
    loaded >> aggregate


# Registers the DAG with Airflow. Easy to forget — without this line the
# scheduler never sees the DAG.
postgres_to_bq_orders()
