"""
Orders router — same shape as items.py, but persisted in Postgres via SQLModel.

A few things to notice vs. items.py (the in-memory version):

  - The dependency we inject is a `Session` (a unit of work / transaction
    handle), not a custom store class. Each request gets its own session
    and it's auto-closed when the handler returns.
  - We build queries with `select(Order)` (SQLModel's typed query DSL) and
    execute them via `session.exec(...)`. Think of it as a typed query
    builder — Prisma's `.findMany({ where })` lives at the same altitude.
  - `session.add(...)` + `session.commit()` is the equivalent of staging
    rows in a transaction and committing. `session.refresh(row)` reloads
    the row so DB-populated fields (id, created_at) come back to the caller.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.db import get_session
from app.models import Message, Order, OrderCreate, OrderStatus

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("", response_model=Order, status_code=status.HTTP_201_CREATED)
def create_order(payload: OrderCreate, session: Session = Depends(get_session)) -> Order:
    order = Order.model_validate(payload)
    session.add(order)
    session.commit()
    session.refresh(order)
    return order


@router.get("", response_model=list[Order])
def list_orders(
    status: OrderStatus | None = None,
    region: str | None = None,
    session: Session = Depends(get_session),
) -> list[Order]:
    query = select(Order)
    if status is not None:
        query = query.where(Order.status == status)
    if region is not None:
        query = query.where(Order.region == region)
    return list(session.exec(query).all())


@router.get("/{order_id}", response_model=Order)
def get_order(order_id: int, session: Session = Depends(get_session)) -> Order:
    order = session.get(Order, order_id)
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order


@router.delete("/{order_id}", response_model=Message)
def delete_order(order_id: int, session: Session = Depends(get_session)) -> Message:
    order = session.get(Order, order_id)
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Order not found")
    session.delete(order)
    session.commit()
    return Message(message=f"Order {order_id} deleted")
