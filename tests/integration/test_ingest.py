import json
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
            openai_api_key="mocked-api-key",  # Provide a mock key for image vision test
        )
        container = build_container(settings)
        app = create_app(container)
        with TestClient(app) as client:
            yield client


@patch("httpx.AsyncClient.get")
def test_ingest_website_success(mock_get: MagicMock, test_client: TestClient) -> None:
    # Mock HTML response from httpx
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "<html><head><title>Test Page Title</title></head><body><h1>Hello World</h1><p>This is a test webpage content.</p></body></html>"
    mock_response.raise_for_status = MagicMock()
    
    # httpx.AsyncClient.get returns an awaitable that yields mock_response
    mock_get.return_value = mock_response

    response = test_client.post(
        "/api/ingest/website",
        json={"url": "https://example.com/test-page"},
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Test Page Title"
    assert "example.com" in data["url"]
    assert data["char_count"] > 0
    assert data["total_in_store"] == 1


def test_ingest_pdf_success(test_client: TestClient) -> None:
    # Mock the PdfExtractor to return a mock extracted string
    with patch("clean_app.infrastructure.extraction.pdf_extractor.PdfExtractor.extract_text") as mock_extract:
        mock_extract.return_value = "Extracted text content from mock PDF document."

        # Create tiny mock PDF file bytes
        mock_pdf_bytes = b"%PDF-1.4 ... dummy pdf content ..."
        
        response = test_client.post(
            "/api/ingest/pdf",
            files={"file": ("sample.pdf", mock_pdf_bytes, "application/pdf")},
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "sample.pdf"
        assert "sample.pdf" in data["url"]
        assert data["char_count"] == len("Extracted text content from mock PDF document.")
        assert data["total_in_store"] == 1


def test_ingest_pdf_invalid_format(test_client: TestClient) -> None:
    response = test_client.post(
        "/api/ingest/pdf",
        files={"file": ("sample.txt", b"plain text content", "text/plain")},
    )
    assert response.status_code == 400
    assert "Only PDF files (.pdf) are supported" in response.json()["detail"]


@patch("openai.AsyncOpenAI")
def test_ingest_image_success(mock_async_openai: MagicMock, test_client: TestClient) -> None:
    # Set up client and completions.create mocks
    mock_client = MagicMock()
    mock_async_openai.return_value = mock_client
    
    # completions.create must be an AsyncMock since it is awaited
    mock_completions = AsyncMock()
    mock_client.chat.completions.create = mock_completions
    
    # Mock OpenAI Vision API Response
    mock_choice = MagicMock()
    mock_choice.message.content = "This is the transcribed text from the parsed image."
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    
    mock_completions.return_value = mock_response

    # Dummy image bytes
    mock_image_bytes = b"dummy image bytes"
    
    response = test_client.post(
        "/api/ingest/image",
        files={"file": ("receipt.png", mock_image_bytes, "image/png")},
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "receipt.png"
    assert "receipt.png" in data["url"]
    assert data["char_count"] == len("This is the transcribed text from the parsed image.")
    assert data["total_in_store"] == 1


def test_ingest_image_invalid_format(test_client: TestClient) -> None:
    response = test_client.post(
        "/api/ingest/image",
        files={"file": ("receipt.txt", b"plain text", "text/plain")},
    )
    assert response.status_code == 400
    assert "Supported image types" in response.json()["detail"]
