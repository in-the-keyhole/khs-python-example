"""
Item models — request/response schemas for the in-memory items slice.

Plain Pydantic models (think Zod / TypeBox): FastAPI uses them for validation,
serialization, AND the auto-generated OpenAPI docs at /docs. A request body
that doesn't match gets a detailed 422 for free — no hand-written guards.

Static data only, by design: no methods, no behavior. The validation here is
declarative schema, not logic — logic lives in services/controllers.
"""

from pydantic import BaseModel
from pydantic import Field as PydanticField


class ItemCreate(BaseModel):
    name: str = PydanticField(min_length=1, max_length=100)
    price: float = PydanticField(gt=0)
    in_stock: bool = True


class Item(ItemCreate):
    id: int
