"""
Pydantic models = your request/response schemas.

Think of these like Zod or TypeBox in Node, except FastAPI uses them for
validation, serialization, AND auto-generated OpenAPI docs at /docs.

If a request body doesn't match the model, FastAPI returns a 422 with a
detailed error — you never have to write `if (!body.name) return res.status(400)`.
"""

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel
from pydantic import Field as PydanticField
from sqlalchemy import Column, DateTime, String
from sqlmodel import Field, SQLModel


class ItemCreate(BaseModel):
    name: str = PydanticField(min_length=1, max_length=100)
    price: float = PydanticField(gt=0)
    in_stock: bool = True


class Item(ItemCreate):
    id: int


class Message(BaseModel):
    message: str


# ──────────────────────────────────────────────────────────────────────────────
# Orders — backed by Postgres via SQLModel (SQLAlchemy + Pydantic in one).
#
# OrderStatus is a typing.Literal rather than an Enum so Pydantic serializes
# it as a plain JSON string ("paid") instead of {"value": "paid"}-style noise.
# ──────────────────────────────────────────────────────────────────────────────

OrderStatus = Literal["pending", "paid", "shipped", "cancelled"]


class OrderCreate(SQLModel):
    customer_id: int
    total_cents: int = Field(gt=0)
    status: OrderStatus = "pending"
    region: str = Field(min_length=1)


class Order(OrderCreate, table=True):
    __tablename__ = "orders"

    id: int | None = Field(default=None, primary_key=True)
    # SQLModel can't build a column from a `typing.Literal` directly, so we
    # override `status` here with a plain VARCHAR at the SQL level. Pydantic
    # still enforces the allowed values via OrderStatus on input.
    status: OrderStatus = Field(
        default="pending",
        sa_column=Column(String, nullable=False),
    )
    # Force TIMESTAMPTZ (vs. SQLModel's default TIMESTAMP WITHOUT TIME ZONE)
    # so the column type matches our PG → BQ contract.
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
