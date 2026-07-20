import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from clean_app.infrastructure.config.settings import Settings
from clean_app.presentation.api.app import create_app
from clean_app.presentation.api.dependencies import build_container


@pytest.fixture
def test_client() -> TestClient:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
        settings = Settings(
            chroma_persist_dir=str(Path(tmp_dir) / "chroma"),
            auto_index_trips=False,
            trip_source="static",
            app_env="test",
            openai_api_key="mocked-api-key",
        )
        container = build_container(settings)
        app = create_app(container)
        with TestClient(app) as client:
            yield client


def test_train_faq_success(test_client: TestClient) -> None:
    payload = {
        "items": [
            {
                "question": "What is the cancellation policy?",
                "answer": "100% refund up to 15 days before departure.",
                "category": "Refunds"
            },
            {
                "question": "Are bike rides included?",
                "answer": "Yes, bike rides in Ladakh are fully supported.",
                "category": "Trips"
            }
        ]
    }
    response = test_client.post("/api/train/faq", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "success"
    assert data["source_type"] == "faq"
    assert data["processed_count"] == 2
    assert data["total_in_vector_store"] == 2


def test_train_pdf_success(test_client: TestClient) -> None:
    with patch("clean_app.infrastructure.extraction.pdf_extractor.PdfExtractor.extract_text") as mock_extract:
        mock_extract.return_value = "PDF guide for Jaipur heritage tours and places to visit."
        mock_pdf_bytes = b"%PDF-1.4 sample content"

        response = test_client.post(
            "/api/train/pdf",
            files={"file": ("jaipur_guide.pdf", mock_pdf_bytes, "application/pdf")},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "success"
        assert data["source_type"] == "pdf"
        assert data["processed_count"] == 1
        assert data["details"]["title"] == "jaipur_guide.pdf"


@patch("httpx.AsyncClient.get")
def test_train_website_success(mock_get: MagicMock, test_client: TestClient) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "<html><head><title>Goa Beach Guide</title></head><body><p>Explore South Goa beaches and watersports.</p></body></html>"
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    response = test_client.post(
        "/api/train/website",
        json={"url": "https://trvios.com/goa-guide"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "success"
    assert data["source_type"] == "website"
    assert data["details"]["title"] == "Goa Beach Guide"


def test_train_mongodb_trips_success(test_client: TestClient) -> None:
    response = test_client.post("/api/train/mongodb-trips")
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "success"
    assert data["source_type"] == "mongodb_trips"
    assert data["processed_count"] >= 0


def test_itinerary_plan_api(test_client: TestClient) -> None:
    payload = {
        "destination": "Goa",
        "duration_days": 4,
        "budget_level": "moderate",
        "travel_style": "beach & relax",
        "interests": ["beaches", "seafood"],
        "companions": "friends"
    }
    response = test_client.post("/api/itinerary/plan", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["destination"] == "Goa"
    assert data["duration_days"] == 4
    assert len(data["days"]) == 4
    assert data["budget_estimate_inr"] > 0
    assert "summary" in data


def test_sync_chat_api(test_client: TestClient) -> None:
    # First train on FAQ
    faq_payload = {
        "items": [
            {
                "question": "What is the best time to visit Udaipur?",
                "answer": "October to March is ideal for visiting Udaipur.",
                "category": "Weather"
            }
        ]
    }
    test_client.post("/api/train/faq", json=faq_payload)

    # Call synchronous chat
    chat_payload = {
        "query": "Tell me about trips to Udaipur",
        "top_k": 3,
        "session_id": "test_session_sync"
    }
    response = test_client.post("/api/chat", json=chat_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["query"] == chat_payload["query"]
    assert "answer" in data
    assert "intent" in data
    assert "validation" in data


def test_unified_1_api_sync_all(test_client: TestClient) -> None:
    """Test 1 Single API Endpoint performing FAQ train, MongoDB train, Chat, and Itinerary in one synchronous call."""
    unified_payload = {
        "action": "sync_all",
        "faq_items": [
            {
                "question": "What is the policy for Manali trip?",
                "answer": "Manali packages include hotel stay and local sightseeing."
            }
        ],
        "sync_mongodb": True,
        "query": "Tell me about Manali trips",
        "destination": "Manali",
        "duration_days": 3,
        "budget_level": "moderate",
        "travel_style": "mountains"
    }

    response = test_client.post("/api/unified", json=unified_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "faq" in data["training_summary"]
    assert data["training_summary"]["faq"]["added_count"] == 1
    assert data["chat_response"] is not None
    assert "Manali" in data["chat_response"]["query"]
    assert data["itinerary_response"] is not None
    assert data["itinerary_response"]["destination"] == "Manali"
    assert len(data["itinerary_response"]["days"]) == 3
