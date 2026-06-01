"""
Entry point — analogous to `app.js` / `server.js` in Express or Fastify.

Run with:  uvicorn app.main:app --reload

`uvicorn` is the ASGI server (think of it as Node's `node` runtime + listener
rolled in one). It hosts the `app` object exported below.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.clients.datadog import metrics
from app.clients.db import create_all
from app.middleware.metrics import RequestMetricsMiddleware
from app.routers import demo, items, orders, streaming


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Startup/shutdown hook — like Express's `app.listen` callback, but symmetric.

    Code before `yield` runs on startup; code after runs on shutdown. We use
    it to materialize the orders table on first boot (dev convenience).
    """
    create_all()
    yield


app = FastAPI(
    title="khs-python-example",
    description="A tiny FastAPI server to learn Python web development.",
    version="0.1.0",
    lifespan=lifespan,
)

# Emit per-request throughput + latency metrics to Datadog (no-ops unless
# DD_METRICS_ENABLED). Pass the process-wide metrics client explicitly so it's
# easy to swap for a fake in tests.
app.add_middleware(RequestMetricsMiddleware, metrics=metrics)


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "Hello from FastAPI. See /docs for the interactive API."}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(items.router)
app.include_router(streaming.router)
app.include_router(demo.router)
app.include_router(orders.router)
