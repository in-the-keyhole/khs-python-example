"""
A router = an Express Router / Fastify plugin. Group related routes here,
then mount onto the main app with a URL prefix.

Key things to notice vs. Express:

  - Decorators (@router.get) replace `router.get(...)` — same idea, different
    syntax. The function below the decorator is the handler.
  - Type hints on parameters drive behavior. FastAPI inspects the signature
    and figures out: is this a path param? Query string? Request body?
    A dependency? You don't pull anything off a `req` object yourself.
  - Return a dict or Pydantic model and FastAPI serializes to JSON. No
    `res.json(...)` needed.
  - To return a non-200, raise HTTPException — like `throw` in Express
    with error middleware, but built in.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.models import Item, ItemCreate, Message
from app.storage import ItemStore, get_store

router = APIRouter(prefix="/items", tags=["items"])


@router.get("", response_model=list[Item])
def list_items(store: ItemStore = Depends(get_store)) -> list[Item]:
    return store.list()


@router.get("/{item_id}", response_model=Item)
def get_item(item_id: int, store: ItemStore = Depends(get_store)) -> Item:
    item = store.get(item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Item not found")
    return item


@router.post("", response_model=Item, status_code=status.HTTP_201_CREATED)
def create_item(payload: ItemCreate, store: ItemStore = Depends(get_store)) -> Item:
    return store.create(payload)


@router.delete("/{item_id}", response_model=Message)
def delete_item(item_id: int, store: ItemStore = Depends(get_store)) -> Message:
    if not store.delete(item_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Item not found")
    return Message(message=f"Item {item_id} deleted")
