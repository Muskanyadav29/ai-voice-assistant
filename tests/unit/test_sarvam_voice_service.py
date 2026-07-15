"""Unit tests for VoiceService routing and fallbacks."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from clean_app.infrastructure.ai.tts_stt_service import VoiceService
from clean_app.infrastructure.config.settings import Settings


def test_voice_service_initialization() -> None:
    settings = Settings(openai_api_key="mock_openai_key", sarvam_api_key="mock_sarvam_key")
    service = VoiceService(settings)
    
    assert service._openai_key == "mock_openai_key"
    assert service._sarvam_api_key == "mock_sarvam_key"
    assert service._client is not None


@patch("clean_app.infrastructure.ai.tts_stt_service.httpx.AsyncClient")
def test_transcribe_audio_uses_sarvam_when_key_present(mock_client_class) -> None:
    # Setup mock response for Sarvam STT POST request
    mock_client = mock_client_class.return_value
    mock_response = MagicMock()
    mock_response.json.return_value = {"transcript": "Hello from Sarvam"}
    mock_response.raise_for_status = MagicMock()
    mock_client.post = AsyncMock(return_value=mock_response)

    settings = Settings(openai_api_key=None, sarvam_api_key="mock_sarvam_key")
    service = VoiceService(settings)
    
    transcript = asyncio.run(service.transcribe_audio(b"fake_audio_bytes"))
    
    assert transcript == "Hello from Sarvam"
    mock_client.post.assert_called_once()
    assert "https://api.sarvam.ai/speech-to-text" in mock_client.post.call_args[0][0]


@patch("clean_app.infrastructure.ai.tts_stt_service.httpx.AsyncClient")
def test_generate_speech_uses_sarvam_when_key_present(mock_client_class, tmp_path) -> None:
    # Setup mock response for Sarvam TTS POST request returning base64 encoded audio
    mock_client = mock_client_class.return_value
    mock_response = MagicMock()
    mock_response.json.return_value = {"audio_content": "VGVzdCBBdWRpbw=="}  # "Test Audio" base64
    mock_response.raise_for_status = MagicMock()
    mock_client.post = AsyncMock(return_value=mock_response)

    settings = Settings(openai_api_key=None, sarvam_api_key="mock_sarvam_key")
    service = VoiceService(settings)
    # Redirect cache dir to tmp_path to prevent contaminating actual caches
    service._cache_dir = tmp_path
    
    audio_bytes = asyncio.run(service.generate_speech("Speak to me"))
    
    assert audio_bytes == b"Test Audio"
    mock_client.post.assert_called_once()
    assert "https://api.sarvam.ai/text-to-speech" in mock_client.post.call_args[0][0]


def test_graceful_empty_fallback_without_keys() -> None:
    settings = Settings(openai_api_key=None, sarvam_api_key=None)
    service = VoiceService(settings)
    
    transcript = asyncio.run(service.transcribe_audio(b"some_audio"))
    speech = asyncio.run(service.generate_speech("text"))
    
    assert transcript == ""
    assert speech == b""
