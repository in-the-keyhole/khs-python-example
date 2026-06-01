"""
conftest.py is a magic filename — pytest auto-loads it. Fixtures defined
here are available to every test in this directory (and subdirectories)
without imports.

Fixtures are pytest's superpower. Think of them as Jest's beforeEach /
beforeAll, but composable: a test function just *names* the fixture as
a parameter and pytest wires it up.

    def test_thing(client):       # pytest sees `client`, finds the fixture,
        client.get("/")           # calls it, passes result here.

Default scope is per-test — each test gets a fresh fixture, so no shared
state surprises. Override with @pytest.fixture(scope="session") for
expensive setup like spinning up a real database.
"""

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.db import get_session
from app.main import app
from app.storage import ItemStore, get_store

# The throwaway Postgres from compose's `test` profile (see compose.yaml).
# `poe test:int` brings it up on 5433 before running the integration suite.
DEFAULT_TEST_DATABASE_URL = "postgresql+psycopg://app:app@localhost:5433/orders"


@pytest.fixture
def store() -> ItemStore:
    """A fresh in-memory store for each test — no leftover state."""
    return ItemStore()


@pytest.fixture
def client(store: ItemStore) -> Iterator[TestClient]:
    """
    A TestClient wired to use our per-test `store` instead of the module-level
    singleton. `dependency_overrides` is FastAPI's testing seam — same trick
    you'd use to swap a real database for a fake one in tests.
    """
    app.dependency_overrides[get_store] = lambda: store
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def session() -> Iterator[Session]:
    """
    An isolated in-memory SQLite database per test — the orders router's
    `get_session` dependency gets pointed at this instead of Postgres, so the
    suite needs no running database.

    StaticPool keeps a single shared connection alive for the lifetime of the
    fixture (in-memory SQLite is per-connection, so without this the schema
    would vanish between requests). A brand-new engine per test guarantees no
    state leaks across tests.
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s
    engine.dispose()  # close the pooled connection so no ResourceWarning leaks


@pytest.fixture
def orders_client(session: Session) -> Iterator[TestClient]:
    """
    A TestClient with the DB `get_session` dependency overridden to use the
    per-test SQLite `session` above — the same seam as `client`, one layer
    down at the database instead of the in-memory store.
    """
    app.dependency_overrides[get_session] = lambda: session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


# ──────────────────────────────────────────────────────────────────────────────
# Integration fixtures — real, prod-like Postgres (vs. the SQLite `session`
# above). Used only by tests marked `@pytest.mark.integration`, which run via
# `uv run poe test:int`. The SQLite fixtures stay the fast default for unit
# tests; these trade speed for fidelity (real TIMESTAMPTZ, real SQL dialect,
# real constraint enforcement).
# ──────────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def pg_engine() -> Iterator[object]:
    """
    A session-scoped engine pointed at the throwaway test Postgres. Creates the
    schema once for the whole run and drops it at the end. If the database
    isn't reachable, every integration test is skipped with a pointer to the
    right command rather than erroring out.
    """
    url = os.environ.get("TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL)
    engine = create_engine(url)
    try:
        with engine.connect():
            pass
    except OperationalError as exc:
        engine.dispose()
        pytest.skip(
            f"integration Postgres not reachable at {url} — start it with "
            f"`uv run poe test:int` (or `docker compose --profile test up -d --wait "
            f"postgres-test`). Original error: {exc}",
            allow_module_level=True,
        )
    SQLModel.metadata.create_all(engine)
    try:
        yield engine
    finally:
        SQLModel.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def pg_session(pg_engine) -> Iterator[Session]:
    """
    A per-test Session wrapped in an outer transaction that is always rolled
    back at teardown, so the shared Postgres database returns to empty between
    tests. `join_transaction_mode="create_savepoint"` lets the handlers call
    `session.commit()` for real (committing into a SAVEPOINT) while the outer
    transaction still unwinds everything on rollback — fast isolation with no
    DDL or truncation per test.
    """
    connection = pg_engine.connect()
    transaction = connection.begin()
    pg = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield pg
    finally:
        pg.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def integration_client(pg_session: Session) -> Iterator[TestClient]:
    """A TestClient whose `get_session` is backed by the rolled-back Postgres session."""
    app.dependency_overrides[get_session] = lambda: pg_session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
