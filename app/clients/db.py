"""
Database wiring for the orders slice.

Coming from Node? Map this to ORMs you already know:

  - `engine` is the connection pool — same idea as a Prisma client or a
    TypeORM DataSource. One per process, created once at import time.
  - `Session` is a unit of work — the same role as a Prisma transaction or
    a TypeORM EntityManager / QueryRunner. You open one per request, run
    your reads and writes against it, and close it at the end.
  - `get_session()` is the FastAPI dependency that hands a fresh Session
    to every handler. The `with ... as s: yield s` pattern guarantees the
    session is closed even if the handler raises — analogous to wrapping
    a Prisma `$transaction` in try/finally.
  - `create_all()` is the dev-time "sync schema from models" helper, the
    rough equivalent of `prisma db push` for prototyping. We call it on
    app startup via a lifespan handler, NOT at import time — importing
    this module must not touch the database.
"""

import os

from sqlmodel import Session, SQLModel, create_engine

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://app:app@localhost:5432/orders",
)

engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)


def get_session():
    """FastAPI dependency: yield a Session and ensure it gets closed."""
    with Session(engine) as session:
        yield session


def create_all() -> None:
    """Create all SQLModel tables. Call from the app lifespan, not at import."""
    SQLModel.metadata.create_all(engine)
