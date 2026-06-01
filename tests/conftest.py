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

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.storage import ItemStore, get_store


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
