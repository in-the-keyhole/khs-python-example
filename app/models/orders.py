"""
Order models — schemas for the Postgres-backed orders slice, built on SQLModel
(SQLAlchemy + Pydantic in one class).

`OrderCreate` is the input schema; `Order` is the same shape plus the DB-managed
columns (`id`, `created_at`) and is the actual table (`table=True`). Static data
only — persistence logic lives in `app.services.orders`, not here.

OrderStatus is a typing.Literal rather than an Enum so Pydantic serializes it as
a plain JSON string ("paid") instead of {"value": "paid"}-style noise.
"""

from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import Column, DateTime, String
from sqlmodel import Field, SQLModel

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
