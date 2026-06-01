"""
Unit tests — exercise `ItemStore` directly, no HTTP, no FastAPI. The fastest
kind of test. Run only these with:

    uv run pytest tests/test_storage.py
"""

from app.models import ItemCreate
from app.storage import ItemStore


def test_new_store_is_empty():
    assert ItemStore().list() == []


def test_create_assigns_incrementing_ids():
    store = ItemStore()
    first = store.create(ItemCreate(name="a", price=1.0))
    second = store.create(ItemCreate(name="b", price=2.0))
    assert (first.id, second.id) == (1, 2)


def test_get_returns_the_created_item():
    store = ItemStore()
    created = store.create(ItemCreate(name="widget", price=9.99))
    assert store.get(created.id) == created


def test_get_returns_none_when_missing():
    assert ItemStore().get(999) is None


def test_delete_removes_the_item():
    store = ItemStore()
    created = store.create(ItemCreate(name="x", price=1.0))
    assert store.delete(created.id) is True
    assert store.get(created.id) is None


def test_delete_returns_false_when_missing():
    assert ItemStore().delete(999) is False
