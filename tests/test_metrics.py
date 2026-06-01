"""
Tests for the Datadog metrics client and the orders endpoint's instrumentation.

Two layers:
  - Unit: the `MetricsClient` wrapper no-ops when disabled and forwards to the
    underlying DogStatsD when enabled (no real UDP — the statsd is mocked).
  - API: `POST /orders` emits the expected metrics, verified by overriding the
    `get_metrics` dependency with a recording fake — the same DI seam used for
    the DB session and item store elsewhere in the suite.

Crucially, nothing here opens a socket or needs an Agent: metrics default to
OFF, and we inject fakes for the rest.
"""

from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.clients.datadog import MetricsClient, get_metrics
from app.clients.db import get_session
from app.main import app
from app.middleware.metrics import RequestMetricsMiddleware


def test_disabled_client_is_noop():
    client = MetricsClient(None)
    assert client.enabled is False
    # No statsd, no socket — these must be harmless no-ops, not errors.
    client.increment("orders.created")
    client.gauge("queue.depth", 5)
    client.histogram("orders.total_cents", 1999)


def test_from_env_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("DD_METRICS_ENABLED", raising=False)
    assert MetricsClient.from_env().enabled is False


def test_from_env_enables_when_flag_set(monkeypatch):
    monkeypatch.setenv("DD_METRICS_ENABLED", "true")
    client = MetricsClient.from_env()
    assert client.enabled is True


def test_enabled_client_forwards_to_statsd():
    statsd = MagicMock()
    client = MetricsClient(statsd)

    client.increment("orders.created", tags=["region:us-west"])
    statsd.increment.assert_called_once_with("orders.created", value=1, tags=["region:us-west"])

    client.histogram("orders.total_cents", 1999, tags=["region:us-west"])
    statsd.histogram.assert_called_once_with("orders.total_cents", 1999, tags=["region:us-west"])


class RecordingMetrics(MetricsClient):
    """A fake client that records calls instead of sending them, for assertions."""

    def __init__(self) -> None:
        super().__init__(None)
        self.calls: list[tuple] = []

    def increment(self, metric, value=1, tags=None):
        self.calls.append(("increment", metric, value, tags))

    def histogram(self, metric, value, tags=None):
        self.calls.append(("histogram", metric, value, tags))


def test_create_order_emits_metrics(session: Session):
    recorder = RecordingMetrics()
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_metrics] = lambda: recorder
    try:
        client = TestClient(app)
        response = client.post(
            "/orders",
            json={"customer_id": 1, "total_cents": 1999, "region": "us-west"},
        )
        assert response.status_code == 201
    finally:
        app.dependency_overrides.clear()

    emitted = [(kind, metric) for kind, metric, *_ in recorder.calls]
    assert ("increment", "orders.created") in emitted
    assert ("histogram", "orders.total_cents") in emitted

    # Tags carry the dimensions you'd group/filter by in Datadog.
    increment_call = next(c for c in recorder.calls if c[1] == "orders.created")
    assert "region:us-west" in increment_call[3]
    assert "status:pending" in increment_call[3]


# ──────────────────────────────────────────────────────────────────────────────
# Request-metrics middleware
# ──────────────────────────────────────────────────────────────────────────────


def _app_with_metrics_middleware(recorder: RecordingMetrics) -> FastAPI:
    """A minimal app wrapped in the middleware, for testing it in isolation."""
    test_app = FastAPI()
    test_app.add_middleware(RequestMetricsMiddleware, metrics=recorder)

    @test_app.get("/ping")
    def ping():
        return {"pong": True}

    @test_app.get("/things/{thing_id}")
    def get_thing(thing_id: int):
        return {"id": thing_id}

    @test_app.get("/stream")
    def stream():
        def gen():
            for i in range(3):
                yield f"chunk{i}\n"

        return StreamingResponse(gen(), media_type="text/plain")

    return test_app


def test_middleware_emits_throughput_and_latency():
    recorder = RecordingMetrics()
    client = TestClient(_app_with_metrics_middleware(recorder))

    assert client.get("/ping").status_code == 200

    kinds = {(kind, metric) for kind, metric, *_ in recorder.calls}
    assert ("increment", "http.requests") in kinds
    assert ("histogram", "http.request.duration_ms") in kinds

    counter = next(c for c in recorder.calls if c[1] == "http.requests")
    tags = counter[3]
    assert "method:GET" in tags
    assert "path:/ping" in tags
    assert "status:200" in tags


def test_middleware_tags_route_template_not_raw_path():
    recorder = RecordingMetrics()
    client = TestClient(_app_with_metrics_middleware(recorder))

    client.get("/things/123")

    counter = next(c for c in recorder.calls if c[1] == "http.requests")
    # Bounded cardinality: the template, not the concrete id.
    assert "path:/things/{thing_id}" in counter[3]
    assert "path:/things/123" not in counter[3]


def test_middleware_preserves_streaming():
    recorder = RecordingMetrics()
    client = TestClient(_app_with_metrics_middleware(recorder))

    response = client.get("/stream")
    assert response.status_code == 200
    # The full streamed body comes through — the middleware didn't buffer/break it.
    assert response.text == "chunk0\nchunk1\nchunk2\n"
    # And it still recorded metrics for the streamed request.
    assert any(c[1] == "http.requests" for c in recorder.calls)
