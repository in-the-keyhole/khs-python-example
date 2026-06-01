"""
Models — the static data schemas (request/response + DB tables) for the app.

Split by slice so each file stays small and focused:

  - `items`  — `ItemCreate`, `Item`           (in-memory items slice)
  - `orders` — `OrderStatus`, `OrderCreate`, `Order`  (Postgres orders slice)
  - `common` — `Message`                       (shared response envelope)

Everything is re-exported here, so callers import from the package namespace
(`from app.models import Item, Order, Message`) and don't need to know which
file a model lives in.

These are FastAPI's validation + serialization + OpenAPI schemas (think Zod /
TypeBox). Static data only — no methods, no behavior; logic lives in
`app.services` / `app.controllers`.
"""

from app.models.common import Message
from app.models.items import Item, ItemCreate
from app.models.orders import Order, OrderCreate, OrderStatus

__all__ = [
    "Item",
    "ItemCreate",
    "Message",
    "Order",
    "OrderCreate",
    "OrderStatus",
]
