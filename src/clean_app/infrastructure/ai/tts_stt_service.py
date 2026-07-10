"""Whisper and Sarvam AI voice implementations for Speech-to-Text and Text-to-Speech with translation support."""

import base64
import hashlib
import io
from pathlib import Path
import httpx
from openai import AsyncOpenAI

from clean_app.infrastructure.config.settings import Settings
from clean_app.infrastructure.config.logging import get_logger

logger = get_logger(__name__)


class VoiceService:
    """Service to handle speech transcription (STT) and voice replies (TTS) using Sarvam AI or OpenAI."""

    def __init__(self, settings: Settings) -> None:
        self._openai_key = settings.openai_api_key
        self._sarvam_api_key = settings.sarvam_api_key
        self._client = AsyncOpenAI(api_key=self._openai_key) if self._openai_key else None
        self._cache_dir = Path("./data/tts_cache")
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._http_client = httpx.AsyncClient(timeout=6.0)

    async def translate_text(self, text: str, source_lang: str, target_lang: str) -> str:
        """Translate text between target languages using OpenAI's gpt-4o-mini."""
        if not text.strip() or not self._client:
            return text
        try:
            prompt = (
                f"You are a precise, context-aware translator. Translate the user's travel query "
                f"from {source_lang} to {target_lang}. Preserve proper nouns, place names, and numbers. "
                "Output ONLY the raw translated text. Do not add explanations, conversational headers, quotes, or formatting."
            )
            response = await self._client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": text}
                ],
                temperature=0.0,
            )
            translated = response.choices[0].message.content.strip()
            logger.info(f"[Translation Service] Translated: '{text}' -> '{translated}' ({source_lang} -> {target_lang})")
            return translated
        except Exception as e:
            logger.error(f"Translation error: {e}", exc_info=True)
            return text

    async def transcribe_audio(self, audio_bytes: bytes, filename: str = "voice.webm", language: str = "hi-IN") -> str:
        """Transcribe speech audio bytes using Sarvam AI or OpenAI Whisper and translate to English if a foreign language is used."""
        if not audio_bytes:
            return ""

        transcript = ""
        
        # 1. Try Sarvam AI STT (optimized specifically for Indic Hinglish/Hindi and English)
        if self._sarvam_api_key and ("hi" in language.lower() or "en" in language.lower()):
            try:
                headers = {"api-subscription-key": self._sarvam_api_key}
                files = {"file": (filename, audio_bytes, "audio/webm")}
                
                # Map en-US or others to en-IN for Sarvam, hi-IN remains hi-IN
                sarvam_lang = "en-IN" if "en" in language.lower() else "hi-IN"
                
                data = {
                    "model": "saaras:v3",
                    "mode": "transcribe",
                    "language": sarvam_lang,
                }
                
                response = await self._http_client.post(
                    "https://api.sarvam.ai/speech-to-text",
                    headers=headers,
                    files=files,
                    data=data,
                )
                response.raise_for_status()
                payload = response.json()
                transcript = payload.get("transcript", payload.get("text", "")).strip()
                if transcript:
                    logger.info(f"[Sarvam STT] Transcribed: {transcript}")
            except Exception as e:
                logger.warning(f"Sarvam AI speech-to-text failed: {e}. Falling back to OpenAI...")

        # 2. General handler for non-Indic languages or fallback using OpenAI Whisper
        if not transcript and self._client:
            try:
                audio_file = io.BytesIO(audio_bytes)
                audio_file.name = filename
                lang_code = language.split("-")[0]
                
                # Call OpenAI Whisper transcription with language guidance
                response = await self._client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language=lang_code,
                )
                transcript = response.text.strip()
                logger.info(f"[Whisper STT] Transcribed ({language}): {transcript}")
            except Exception as e:
                logger.error(f"OpenAI Whisper transcription failed: {e}", exc_info=True)

        if not transcript:
            return ""

        # 3. Translate transcription to English if language is foreign (e.g. Spanish, French, German)
        if any(lang in language.lower() for lang in ["es-", "fr-", "de-"]):
            translated_transcript = await self.translate_text(transcript, language, "English")
            logger.info(f"[Multilingual VAD] Transferred non-English input '{transcript}' -> English: '{translated_transcript}'")
            return translated_transcript

        return transcript

    async def generate_speech(self, text: str, language: str = "hi-IN") -> bytes:
        """Generate speech audio from text. Translates text to the target language if a foreign language is used."""
        if not text.strip():
            return b""

        # 1. Translate if target language is foreign
        target_text = text
        if any(lang in language.lower() for lang in ["es-", "fr-", "de-"]):
            target_text = await self.translate_text(text, "English", language)
            logger.info(f"[Multilingual TTS] Translating answer to {language} for speaker: {target_text}")

        # Compute MD5 hash of target text and language to use as cache key
        text_hash = hashlib.md5(f"{target_text}_{language}".encode("utf-8")).hexdigest()
        cache_path = self._cache_dir / f"{text_hash}.mp3"

        # Check if already in cache
        if cache_path.exists():
            return cache_path.read_bytes()

        # 2. Try Sarvam AI TTS (only for English/Hindi)
        if self._sarvam_api_key and ("hi" in language.lower() or "en" in language.lower()):
            try:
                headers = {
                    "api-subscription-key": self._sarvam_api_key,
                    "Content-Type": "application/json",
                }
                # Determine language code: use hi-IN if Hindi characters are detected, otherwise en-IN
                target_lang = "hi-IN" if any(ord(char) > 127 for char in target_text) else "en-IN"
                payload = {
                    "text": target_text,
                    "model": "bulbul:v3",
                    "speaker": "Ritu",  # Female voice
                    "target_language_code": target_lang,
                }
                
                response = await self._http_client.post(
                    "https://api.sarvam.ai/text-to-speech",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                
                audio_base64 = data.get("audio_content")
                if not audio_base64 and "audios" in data:
                    audios = data["audios"]
                    if isinstance(audios, list) and audios:
                        audio_base64 = audios[0]

                if audio_base64:
                    audio_bytes = base64.b64decode(audio_base64)
                    cache_path.write_bytes(audio_bytes)
                    logger.info(f"[Sarvam TTS] Generated speech cached ({len(audio_bytes)} bytes)")
                    return audio_bytes
            except Exception as e:
                logger.warning(f"Sarvam AI text-to-speech failed: {e}. Falling back to OpenAI...")

        # 3. Fallback / general handler using OpenAI TTS (excellent dynamic multi-lingual accent support)
        if self._client:
            try:
                # OpenAI tts-1 will naturally choose the correct accent and language matching target_text
                response = await self._client.audio.speech.create(
                    model="tts-1",
                    voice="alloy",
                    input=target_text,
                )
                audio_bytes = await response.aread()
                cache_path.write_bytes(audio_bytes)
                logger.info(f"[OpenAI TTS] Generated speech cached ({len(audio_bytes)} bytes)")
                return audio_bytes
            except Exception as e:
                logger.error(f"OpenAI TTS speech generation failed: {e}", exc_info=True)

        return b""

    def get_cached_speech_path(self, text: str) -> Path | None:
        """Return the path to a cached speech file if it exists."""
        text_hash = hashlib.md5(text.encode("utf-8")).hexdigest()
        cache_path = self._cache_dir / f"{text_hash}.mp3"
        return cache_path if cache_path.exists() else None
