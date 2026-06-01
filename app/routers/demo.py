"""
Tiny lab to *feel* the difference between sync and async on the event loop.

Fire two requests in parallel at each endpoint and time the total:

    # BAD: time.sleep blocks the event loop — two calls serialize to ~6s.
    time (curl -s 'http://127.0.0.1:8000/demo/blocking?seconds=3' & \
          curl -s 'http://127.0.0.1:8000/demo/blocking?seconds=3' & wait)

    # GOOD: asyncio.sleep yields control — two calls overlap, total ~3s.
    time (curl -s 'http://127.0.0.1:8000/demo/async-sleep?seconds=3' & \
          curl -s 'http://127.0.0.1:8000/demo/async-sleep?seconds=3' & wait)

    # ALSO GOOD: plain `def` handler runs on FastAPI's threadpool, so a
    # blocking call inside doesn't freeze the loop — total ~3s.
    time (curl -s 'http://127.0.0.1:8000/demo/threadpool?seconds=3' & \
          curl -s 'http://127.0.0.1:8000/demo/threadpool?seconds=3' & wait)
"""

import asyncio
import time

from fastapi import APIRouter

router = APIRouter(prefix="/demo", tags=["async demo"])


@router.get("/blocking")
async def blocking(seconds: float = 2.0) -> dict[str, str]:
    """BAD: sync sleep inside async def freezes the entire server."""
    time.sleep(seconds)
    return {"verdict": "this blocked the whole server"}


@router.get("/async-sleep")
async def async_sleep(seconds: float = 2.0) -> dict[str, str]:
    """GOOD: asyncio.sleep yields control while waiting."""
    await asyncio.sleep(seconds)
    return {"verdict": "other requests ran while we slept"}


@router.get("/threadpool")
def threadpool(seconds: float = 2.0) -> dict[str, str]:
    """
    Plain `def` handler — FastAPI runs it on a threadpool, so a blocking
    call here is harmless from the outside. Different mechanism than
    asyncio, but the caller can't tell the difference.
    """
    time.sleep(seconds)
    return {"verdict": "ran on threadpool — also non-blocking from outside"}
