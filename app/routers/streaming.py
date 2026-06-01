"""
Streaming responses — analogues to Node's Readable streams / SSE.

The key Python primitive is an *async generator*: an `async def` that uses
`yield` instead of `return`. FastAPI's `StreamingResponse` consumes it and
pushes each yielded chunk to the client as soon as it's produced — the full
body never sits in memory at once.

Try these endpoints with curl (use -N to disable output buffering so you see
chunks as they arrive):

    curl -N http://127.0.0.1:8000/stream/count
    curl -N http://127.0.0.1:8000/stream/events
    curl -N http://127.0.0.1:8000/stream/json | jq -c .
"""

import asyncio
import json
from datetime import UTC, datetime

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/stream", tags=["streaming"])


@router.get("/count")
async def stream_count(to: int = 10, delay: float = 0.3) -> StreamingResponse:
    """Simplest case: yield N text chunks with a small delay between each."""

    async def producer():
        for i in range(1, to + 1):
            yield f"chunk {i} of {to}\n"
            await asyncio.sleep(delay)
        yield "done\n"

    return StreamingResponse(producer(), media_type="text/plain")


@router.get("/events")
async def stream_events(count: int = 20, delay: float = 0.5) -> StreamingResponse:
    """
    Server-Sent Events (SSE) — the format LLM token streams, live logs, and
    progress updates use. The browser's EventSource API parses it natively:

        const es = new EventSource('/stream/events')
        es.onmessage = (e) => console.log(JSON.parse(e.data))
    """

    async def producer():
        for i in range(count):
            payload = {
                "tick": i,
                "timestamp": datetime.now(UTC).isoformat(),
            }
            # SSE wire format is literally "data: <text>\n\n" per event.
            yield f"data: {json.dumps(payload)}\n\n"
            await asyncio.sleep(delay)

    return StreamingResponse(producer(), media_type="text/event-stream")


@router.get("/json")
async def stream_ndjson(count: int = 50) -> StreamingResponse:
    """
    NDJSON (newline-delimited JSON) — one JSON object per line. Easier than
    SSE for batch tooling: pipe through `jq -c .` or read in Python with
    `for line in r.iter_lines(): json.loads(line)`.
    """

    async def producer():
        for i in range(count):
            yield json.dumps({"index": i, "square": i * i}) + "\n"
            # Tiny await lets the event loop interleave other work / flush.
            await asyncio.sleep(0)

    return StreamingResponse(producer(), media_type="application/x-ndjson")
