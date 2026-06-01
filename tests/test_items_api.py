"""
Integration tests via FastAPI's `TestClient`.

`TestClient` is the Python equivalent of Node's `supertest`: it runs your
ASGI app *in-process* (no real network, no real server) and gives you a
requests-like API. Fast (milliseconds), deterministic, and exercises the
full request → routing → validation → handler → response pipeline.

Notice we don't start uvicorn. We don't open a port. We don't make HTTP
requests over the wire. We just call `client.get(...)` and the framework
handles it internally.
"""


def test_root(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "message" in response.json()


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_list_empty(client):
    assert client.get("/items").json() == []


def test_create_and_get(client):
    created = client.post("/items", json={"name": "widget", "price": 9.99}).json()
    assert created["id"] == 1
    assert created["name"] == "widget"
    assert created["in_stock"] is True  # default value applied

    fetched = client.get(f"/items/{created['id']}").json()
    assert fetched == created


def test_get_missing_returns_404(client):
    response = client.get("/items/999")
    assert response.status_code == 404
    assert response.json() == {"detail": "Item not found"}


def test_validation_error_is_422(client):
    response = client.post("/items", json={"name": "", "price": -1})
    assert response.status_code == 422
    # Pydantic gives a detailed list — assert on the shape, not the exact text.
    details = response.json()["detail"]
    fields = {tuple(err["loc"]) for err in details}
    assert ("body", "name") in fields
    assert ("body", "price") in fields


def test_delete_then_404(client):
    created = client.post("/items", json={"name": "x", "price": 1.0}).json()
    assert client.delete(f"/items/{created['id']}").status_code == 200
    assert client.get(f"/items/{created['id']}").status_code == 404


def test_delete_missing_returns_404(client):
    response = client.delete("/items/999")
    assert response.status_code == 404
    assert response.json() == {"detail": "Item not found"}


def test_per_test_isolation(client):
    """
    The `store` fixture is per-test, so this test sees an empty store even
    though earlier tests created items. Compare to Jest's beforeEach.
    """
    assert client.get("/items").json() == []
