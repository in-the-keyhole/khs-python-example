"""
In-memory "database". In real apps you'd swap this for SQLAlchemy, asyncpg,
Mongo, etc. — but for learning, a dict is enough.

Exposed as a singleton instance because FastAPI's dependency injection (see
routers/items.py) will hand the same instance to every request.
"""

from itertools import count

from app.models import Item, ItemCreate


class ItemStore:
    def __init__(self) -> None:
        self._items: dict[int, Item] = {}
        self._ids = count(start=1)

    def list(self) -> list[Item]:
        return list(self._items.values())

    def get(self, item_id: int) -> Item | None:
        return self._items.get(item_id)

    def create(self, data: ItemCreate) -> Item:
        item = Item(id=next(self._ids), **data.model_dump())
        self._items[item.id] = item
        return item

    def delete(self, item_id: int) -> bool:
        return self._items.pop(item_id, None) is not None


store = ItemStore()


def get_store() -> ItemStore:
    return store
