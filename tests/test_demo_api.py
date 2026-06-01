"""
Smoke tests for the async-vs-sync lab (`app/routers/demo.py`).

The *point* of those endpoints is timing behavior under concurrency, which is
demonstrated by hand with curl in the README — not something we assert on here
(wall-clock timing makes for flaky tests). These tests just pin the contract:
each endpoint returns 200 with a `verdict`, for both the blocking and
non-blocking variants. We pass seconds=0 so the suite stays instant.
"""

import pytest


@pytest.mark.parametrize("path", ["/demo/blocking", "/demo/async-sleep", "/demo/threadpool"])
def test_demo_endpoint_returns_verdict(client, path):
    response = client.get(path, params={"seconds": 0})
    assert response.status_code == 200
    assert "verdict" in response.json()
