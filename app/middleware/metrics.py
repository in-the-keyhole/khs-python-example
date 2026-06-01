"""
Request-metrics middleware — emits one set of Datadog metrics for every HTTP
request:

    khs.http.requests             (counter)    — throughput
    khs.http.request.duration_ms  (histogram)  — latency (Datadog derives avg/p95/max)

both tagged `method:` / `path:` / `status:`. This is the app-wide complement to
the per-endpoint metrics in `app/routers/orders.py`: those count a domain event
(an order created), this measures *every* request uniformly.

**Why a pure-ASGI middleware** (not Starlette's `BaseHTTPMiddleware`):
`BaseHTTPMiddleware` buffers the response body, which breaks the streaming
endpoints (`/stream/*`) and skews timing. A raw ASGI middleware only wraps
`send` to read the status line off `http.response.start` — it never touches the
body — so streaming stays intact and the timing covers the whole request.

**Cardinality**: the `path` tag uses the matched *route template*
(`/orders/{order_id}`), never the raw path (`/orders/123`), so the number of
distinct tag values stays bounded by the number of routes. Requests that match
no route are tagged `path:unmatched` rather than echoing arbitrary (often
bot-generated) URLs, which would blow up cardinality.
"""

import time

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.clients.datadog import MetricsClient


class RequestMetricsMiddleware:
    def __init__(self, app: ASGIApp, metrics: MetricsClient) -> None:
        self.app = app
        self.metrics = metrics

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            # Lifespan / websocket events pass straight through.
            await self.app(scope, receive, send)
            return

        start = time.perf_counter()
        status_code = 500  # assume failure until the app sends a status line

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration_ms = (time.perf_counter() - start) * 1000.0
            # `scope["route"]` is populated by FastAPI during routing (above);
            # `.path` is the template. None when nothing matched (404).
            route = scope.get("route")
            path = getattr(route, "path", None) or "unmatched"
            tags = [
                f"method:{scope.get('method', 'UNKNOWN')}",
                f"path:{path}",
                f"status:{status_code}",
            ]
            self.metrics.increment("http.requests", tags=tags)
            self.metrics.histogram("http.request.duration_ms", duration_ms, tags=tags)
