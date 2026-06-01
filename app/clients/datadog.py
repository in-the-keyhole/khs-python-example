"""
Datadog client — emits custom application metrics ("analytics") to Datadog
over DogStatsD.

The flow, in production and in our compose `observability` profile alike:

    app  --UDP-->  Datadog Agent (DogStatsD :8125)  --HTTPS-->  Datadog

The app never holds a Datadog API key — it just fires UDP packets at a local
Agent, which batches and forwards them (the Agent has the key). DogStatsD over
UDP is fire-and-forget: sends never block and never raise, so instrumentation
can't slow down or break a request. This is the same pattern you'd run on GKE
(Agent as a DaemonSet) or Cloud Run (Agent sidecar).

**Safe by default.** Metrics are OFF unless `DD_METRICS_ENABLED` is truthy.
When off — the default for local dev and for the test suite — every method is a
no-op and no socket is ever opened, so the app behaves exactly as if Datadog
weren't wired in at all.

Config is read once from the environment at import time, mirroring how
`clients/db.py` reads `DATABASE_URL`:

    DD_METRICS_ENABLED   "true"/"1"/"yes" to turn metrics on   (default: off)
    DD_AGENT_HOST        Agent host for DogStatsD               (default: localhost)
    DD_DOGSTATSD_PORT    Agent DogStatsD UDP port               (default: 8125)

Service identity uses Datadog's standard "unified service tagging": the
DogStatsD client itself turns DD_SERVICE / DD_ENV / DD_VERSION into
service:/env:/version: tags on every metric. We just default them (to
khs-python-example / local / 0.1.0) when unset, so we never add those tags by
hand and never double them.

Every metric is namespaced under `khs.`, so e.g. `metrics.increment("orders.created")`
lands in Datadog as `khs.orders.created{service:...,env:...,version:...}`.
"""

import os

from datadog.dogstatsd import DogStatsd

METRIC_NAMESPACE = "khs"

_TRUTHY = {"1", "true", "yes", "on"}


class MetricsClient:
    """
    Thin wrapper over DogStatsD that (a) no-ops entirely when metrics are
    disabled and (b) keeps the call sites tiny and uniform. Inject it into a
    view with `Depends(get_metrics)`, the same seam used for the DB session and
    the item store — which also makes it trivial to swap for a recording fake
    in tests.
    """

    def __init__(self, statsd: DogStatsd | None) -> None:
        self._statsd = statsd

    @property
    def enabled(self) -> bool:
        return self._statsd is not None

    @classmethod
    def from_env(cls) -> "MetricsClient":
        if os.environ.get("DD_METRICS_ENABLED", "").lower() not in _TRUTHY:
            return cls(None)  # disabled: no socket, all calls no-op

        # Datadog "unified service tagging": the DogStatsD client automatically
        # turns DD_SERVICE / DD_ENV / DD_VERSION into service:/env:/version:
        # tags on every metric. We only fill in sensible defaults here (respecting
        # anything already set) — adding these tags ourselves would double them.
        os.environ.setdefault("DD_SERVICE", "khs-python-example")
        os.environ.setdefault("DD_ENV", "local")
        os.environ.setdefault("DD_VERSION", "0.1.0")

        statsd = DogStatsd(
            host=os.environ.get("DD_AGENT_HOST", "localhost"),
            port=int(os.environ.get("DD_DOGSTATSD_PORT", "8125")),
            namespace=METRIC_NAMESPACE,
        )
        return cls(statsd)

    def increment(self, metric: str, value: int = 1, tags: list[str] | None = None) -> None:
        """Bump a counter — e.g. count of orders created."""
        if self._statsd is not None:
            self._statsd.increment(metric, value=value, tags=tags)

    def gauge(self, metric: str, value: float, tags: list[str] | None = None) -> None:
        """Record a point-in-time value — e.g. current queue depth."""
        if self._statsd is not None:
            self._statsd.gauge(metric, value, tags=tags)

    def histogram(self, metric: str, value: float, tags: list[str] | None = None) -> None:
        """Record a value Datadog aggregates into avg/median/p95/max — e.g. order size."""
        if self._statsd is not None:
            self._statsd.histogram(metric, value, tags=tags)


# Process-wide singleton — one DogStatsD socket per process, created once.
metrics = MetricsClient.from_env()


def get_metrics() -> MetricsClient:
    """FastAPI dependency: hand views the process-wide metrics client."""
    return metrics
