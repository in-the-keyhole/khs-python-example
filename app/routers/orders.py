"""
Orders router — the "view" for the orders slice. Thin by design: it parses and
validates input (via the typed signature), delegates all persistence to
`app.services.orders`, and shapes the HTTP response (status codes, 404s).

Contrast with items.py: there the injected dependency is a stateful singleton
store; here it's a request-scoped `Session` (a unit of work / transaction
handle) that the view hands to the stateless service functions. Either way the
router holds no data-access logic of its own — that lives a layer down in the
service.

It also emits a couple of Datadog metrics on order creation — a small, honest
demo of "send analytics to Datadog" at the HTTP boundary. (Domain-event metrics
like these could move into an `orders` controller once business logic lands
there; for now the view is the simplest place to show the client + DI seam.)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.clients.datadog import MetricsClient, get_metrics
from app.clients.db import get_session
from app.models import Message, Order, OrderCreate, OrderStatus
from app.services import orders as orders_service

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("", response_model=Order, status_code=status.HTTP_201_CREATED)
def create_order(
    payload: OrderCreate,
    session: Session = Depends(get_session),
    metrics: MetricsClient = Depends(get_metrics),
) -> Order:
    order = orders_service.create(session, payload)
    # Analytics: count orders and track their size, sliced by region/status.
    tags = [f"region:{order.region}", f"status:{order.status}"]
    metrics.increment("orders.created", tags=tags)
    metrics.histogram("orders.total_cents", order.total_cents, tags=tags)
    return order


@router.get("", response_model=list[Order])
def list_orders(
    status: OrderStatus | None = None,
    region: str | None = None,
    session: Session = Depends(get_session),
) -> list[Order]:
    return orders_service.list_orders(session, status=status, region=region)


@router.get("/{order_id}", response_model=Order)
def get_order(order_id: int, session: Session = Depends(get_session)) -> Order:
    order = orders_service.get(session, order_id)
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order


@router.delete("/{order_id}", response_model=Message)
def delete_order(order_id: int, session: Session = Depends(get_session)) -> Message:
    if not orders_service.delete(session, order_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Order not found")
    return Message(message=f"Order {order_id} deleted")
