"""
Integration tests for the `/orders` slice against a *real* Postgres.

These mirror the SQLite-backed `test_orders_api.py`, but run against the
throwaway `postgres-test` container (see compose.yaml + `poe test:int`). The
payoff over SQLite is fidelity: real TIMESTAMPTZ handling, the real SQL
dialect, and real constraint enforcement — the things SQLite silently fakes.

Every test in this module is marked `integration`, so it's deselected from the
default `poe test` run and only executes via `uv run poe test:int`. Per-test
isolation comes from the `pg_session` fixture's transaction rollback, so the
shared database starts empty for each test.
"""

from datetime import datetime

import pytest

pytestmark = pytest.mark.integration


def test_table_starts_empty_each_test(integration_client):
    # Proves the rollback isolation: no rows leak in from other tests.
    assert integration_client.get("/orders").json() == []


def test_create_round_trips_with_tzaware_timestamp(integration_client):
    response = integration_client.post(
        "/orders",
        json={"customer_id": 42, "total_cents": 1999, "region": "us-west"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["id"] is not None
    assert body["status"] == "pending"

    # The Order.created_at column is TIMESTAMPTZ. Real Postgres round-trips a
    # timezone-aware value; SQLite would hand back a naive datetime, so this
    # assertion is exactly the kind of thing the integration suite exists for.
    created_at = datetime.fromisoformat(body["created_at"])
    assert created_at.tzinfo is not None


def test_full_crud_lifecycle(integration_client):
    created = integration_client.post(
        "/orders",
        json={"customer_id": 7, "total_cents": 500, "region": "eu-central"},
    ).json()

    assert integration_client.get(f"/orders/{created['id']}").json() == created

    deleted = integration_client.delete(f"/orders/{created['id']}")
    assert deleted.status_code == 200
    assert integration_client.get(f"/orders/{created['id']}").status_code == 404


def test_list_filters_by_status_and_region(integration_client):
    integration_client.post(
        "/orders",
        json={"customer_id": 1, "total_cents": 100, "region": "us-west", "status": "paid"},
    )
    integration_client.post(
        "/orders",
        json={"customer_id": 2, "total_cents": 200, "region": "us-west", "status": "pending"},
    )
    integration_client.post(
        "/orders",
        json={"customer_id": 3, "total_cents": 300, "region": "eu-central", "status": "paid"},
    )

    matches = integration_client.get(
        "/orders", params={"status": "paid", "region": "us-west"}
    ).json()
    assert [o["customer_id"] for o in matches] == [1]


def test_get_missing_returns_404(integration_client):
    response = integration_client.get("/orders/999")
    assert response.status_code == 404
    assert response.json() == {"detail": "Order not found"}
