"""
Testing streaming endpoints.

`TestClient` returns the full body by default, but for streams you usually
want chunk-by-chunk consumption. Pass `stream=True` and iterate via
`response.iter_lines()` or `response.iter_bytes()`.
"""

import json


def test_count_streams_all_chunks(client):
    with client.stream("GET", "/stream/count?to=3&delay=0") as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/plain")
        lines = [line for line in response.iter_lines() if line]
        assert lines == ["chunk 1 of 3", "chunk 2 of 3", "chunk 3 of 3", "done"]


def test_ndjson_each_line_is_valid_json(client):
    with client.stream("GET", "/stream/json?count=5") as response:
        assert response.status_code == 200
        records = [json.loads(line) for line in response.iter_lines() if line]
    assert len(records) == 5
    assert records[2] == {"index": 2, "square": 4}


def test_events_emits_sse_format(client):
    with client.stream("GET", "/stream/events?count=2&delay=0") as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = response.read().decode()

    # SSE frames: "data: <payload>\n\n"
    data_lines = [line for line in body.splitlines() if line.startswith("data: ")]
    assert len(data_lines) == 2
    payload = json.loads(data_lines[0].removeprefix("data: "))
    assert payload["tick"] == 0
    assert "timestamp" in payload
