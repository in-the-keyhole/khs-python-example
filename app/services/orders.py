"""
Orders service — the persistence logic for the orders slice, lifted out of the
router so the endpoints (the "views") stay thin.

These are stateless module-level functions: no class, no module state. Each
takes the SQLModel `Session` as its first argument — the session is
request-scoped and owned by the view via the `get_session` dependency, so the
service never reaches for one itself. This keeps the service a pure
"classless functional utility": trivially testable (pass a session, call a
function) and free of lifecycle concerns.

Naming note: the list helper is `list_orders`, not `list`, so it doesn't
shadow the builtin we rely on inside the function body.
"""

from sqlmodel import Session, select

from app.models import Order, OrderCreate, OrderStatus


def create(session: Session, payload: OrderCreate) -> Order:
    order = Order.model_validate(payload)
    session.add(order)
    session.commit()
    session.refresh(order)
    return order


def list_orders(
    session: Session,
    status: OrderStatus | None = None,
    region: str | None = None,
) -> list[Order]:
    query = select(Order)
    if status is not None:
        query = query.where(Order.status == status)
    if region is not None:
        query = query.where(Order.region == region)
    return list(session.exec(query).all())


def get(session: Session, order_id: int) -> Order | None:
    return session.get(Order, order_id)


def delete(session: Session, order_id: int) -> bool:
    """Delete an order, returning False if it didn't exist (the view turns that into a 404)."""
    order = session.get(Order, order_id)
    if order is None:
        return False
    session.delete(order)
    session.commit()
    return True
