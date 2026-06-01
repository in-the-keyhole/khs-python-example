"""
Integration tests for the Postgres-backed `/orders` slice.

These look almost identical to `test_items_api.py` even though orders are
persisted via SQLModel and items live in a dict — that's the payoff of the
`dependency_overrides` pattern. The `orders_client` fixture (see conftest.py)
swaps the real Postgres session for a throwaway in-memory SQLite one, so the
handlers, queries, and validation all run for real without a database server.
"""


def test_list_empty(orders_client):
    assert orders_client.get("/orders").json() == []


def test_create_returns_201_with_server_populated_fields(orders_client):
    response = orders_client.post(
        "/orders",
        json={"customer_id": 42, "total_cents": 1999, "region": "us-west"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["id"] is not None  # DB-assigned primary key
    assert body["customer_id"] == 42
    assert body["status"] == "pending"  # default applied
    assert body["created_at"] is not None  # default_factory timestamp


def test_create_and_get_round_trips(orders_client):
    created = orders_client.post(
        "/orders",
        json={"customer_id": 7, "total_cents": 500, "region": "eu-central"},
    ).json()

    fetched = orders_client.get(f"/orders/{created['id']}").json()
    assert fetched == created


def test_get_missing_returns_404(orders_client):
    response = orders_client.get("/orders/999")
    assert response.status_code == 404
    assert response.json() == {"detail": "Order not found"}


def test_delete_then_404(orders_client):
    created = orders_client.post(
        "/orders",
        json={"customer_id": 1, "total_cents": 100, "region": "us-east"},
    ).json()

    deleted = orders_client.delete(f"/orders/{created['id']}")
    assert deleted.status_code == 200
    assert deleted.json() == {"message": f"Order {created['id']} deleted"}
    assert orders_client.get(f"/orders/{created['id']}").status_code == 404


def test_delete_missing_returns_404(orders_client):
    response = orders_client.delete("/orders/999")
    assert response.status_code == 404
    assert response.json() == {"detail": "Order not found"}


def test_list_filters_by_status(orders_client):
    orders_client.post(
        "/orders",
        json={"customer_id": 1, "total_cents": 100, "region": "us-east", "status": "paid"},
    )
    orders_client.post(
        "/orders",
        json={"customer_id": 2, "total_cents": 200, "region": "us-east", "status": "pending"},
    )

    paid = orders_client.get("/orders", params={"status": "paid"}).json()
    assert len(paid) == 1
    assert paid[0]["status"] == "paid"


def test_list_filters_by_region(orders_client):
    orders_client.post(
        "/orders",
        json={"customer_id": 1, "total_cents": 100, "region": "us-west"},
    )
    orders_client.post(
        "/orders",
        json={"customer_id": 2, "total_cents": 200, "region": "eu-central"},
    )

    west = orders_client.get("/orders", params={"region": "us-west"}).json()
    assert len(west) == 1
    assert west[0]["region"] == "us-west"


def test_list_filters_by_status_and_region_together(orders_client):
    orders_client.post(
        "/orders",
        json={"customer_id": 1, "total_cents": 100, "region": "us-west", "status": "paid"},
    )
    orders_client.post(
        "/orders",
        json={"customer_id": 2, "total_cents": 200, "region": "us-west", "status": "pending"},
    )
    orders_client.post(
        "/orders",
        json={"customer_id": 3, "total_cents": 300, "region": "eu-central", "status": "paid"},
    )

    matches = orders_client.get("/orders", params={"status": "paid", "region": "us-west"}).json()
    assert len(matches) == 1
    assert matches[0]["customer_id"] == 1


def test_validation_rejects_bad_body(orders_client):
    # total_cents must be > 0, region must be non-empty.
    response = orders_client.post(
        "/orders",
        json={"customer_id": 1, "total_cents": 0, "region": ""},
    )
    assert response.status_code == 422
    fields = {tuple(err["loc"]) for err in response.json()["detail"]}
    assert ("body", "total_cents") in fields
    assert ("body", "region") in fields


def test_validation_rejects_unknown_status(orders_client):
    response = orders_client.post(
        "/orders",
        json={
            "customer_id": 1,
            "total_cents": 100,
            "region": "us-west",
            "status": "teleported",  # not one of the allowed OrderStatus values
        },
    )
    assert response.status_code == 422
