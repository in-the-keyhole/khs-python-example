"""
Shared models that aren't specific to one slice.

`Message` is the generic response envelope used wherever an endpoint just needs
to acknowledge an action (e.g. a delete) — both the items and orders routers
return it.
"""

from pydantic import BaseModel


class Message(BaseModel):
    message: str
