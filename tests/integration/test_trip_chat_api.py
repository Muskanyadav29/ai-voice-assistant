"""Tests for trip chat API."""

import json
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from clean_app.infrastructure.config.settings import Settings
from clean_app.presentation.api.app import create_app
from clean_app.presentation.api.dependencies import build_container


@pytest.fixture
def api_client() -> TestClient:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
        settings = Settings(
            chroma_persist_dir=str(Path(tmp_dir) / "chroma"),
            auto_index_trips=False,
            trip_source="static",
            app_env="test",
        )
        container = build_container(settings)
        app = create_app(container)
        with TestClient(app) as client:
            yield client


def test_list_trips(api_client: TestClient) -> None:
    response = api_client.get("/api/trips")
    assert response.status_code == 200
    trips = response.json()
    assert len(trips) >= 1
    assert "title" in trips[0]
    assert "price" in trips[0]


def test_index_and_streaming_chat_flow(api_client: TestClient) -> None:
    index_response = api_client.post("/api/trips/index")
    assert index_response.status_code == 200
    indexed = index_response.json()
    assert indexed["total_in_store"] >= 1

    with api_client.stream(
        "POST",
        "/api/chat/stream",
        json={"query": "affordable city trip in Europe", "top_k": 2},
    ) as chat_response:
        assert chat_response.status_code == 200
        assert chat_response.headers["content-type"].startswith("text/event-stream")

        events: list[dict[str, object]] = []
        for line in chat_response.iter_lines():
            if not line or not line.startswith("data: "):
                continue
            events.append(json.loads(line.removeprefix("data: ")))

    event_types = [event["type"] for event in events]
    assert "sources" in event_types
    assert "token" in event_types
    assert event_types[-1] == "done"

    answer = "".join(
        str(event["content"]) for event in events if event.get("type") == "token"
    )
    assert answer

    done_event = events[-1]
    assert isinstance(done_event.get("sources"), list)
    assert len(done_event["sources"]) >= 1


def test_health_reports_index_count(api_client: TestClient) -> None:
    api_client.post("/api/trips/index")
    health = api_client.get("/health")
    assert health.status_code == 200
    assert health.json()["indexed_trips"] >= 1


def test_chat_ui_is_served(api_client: TestClient) -> None:
    response = api_client.get("/")
    assert response.status_code == 200
    assert "Trip Chat" in response.text
    assert "/app.js" in response.text
