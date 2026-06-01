"""
Clients — connections to external systems the app talks to.

Anything that owns a handle to something *outside* the process lives here: the
database engine today, and (later) a cache, a message queue, or a third-party
HTTP API would sit alongside it. Services depend on clients to reach external
state; clients themselves hold no business logic.

  - `db` — the SQLModel/SQLAlchemy engine (connection pool) for Postgres, plus
    the `get_session` DI provider the views inject.
  - `datadog` — a DogStatsD metrics client for sending analytics to Datadog,
    plus the `get_metrics` DI provider. No-ops unless `DD_METRICS_ENABLED`.
"""
