import json
import base64
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Request, UploadFile, File, Form, Query, HTTPException, status
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel

from clean_app.application.dto.trip_dto import ChatRequest
from clean_app.presentation.api.schemas import ChatRequestSchema, TripSourceSchema
from clean_app.infrastructure.config.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


class VoiceChatResponseSchema(BaseModel):
    query: str
    answer: str
    intent: str
    entities: dict[str, Any]
    sources: list[TripSourceSchema]
    audio_base64: str | None = None
    validation: dict[str, bool]


def _format_sse_event(payload: dict[str, object]) -> str:
    return f"data: {json.dumps(payload)}\n\n"


async def check_user_safety_and_limits(
    request: Request,
    query: str,
    session_id: str
) -> tuple[bool, str]:
    """Checks user blocking, rate limiting, and spam safety.

    Raises HTTPException for blocked/limited requests.
    Returns (is_safe, warning_msg).
    """
    container = request.app.state.container
    mongo_repo = container.mongo_safety_repository
    safety_service = container.safety_service
    settings = container.settings

    # Identify user by client IP address, fallback to session_id
    client_ip = request.client.host if request.client else "unknown"
    user_key = client_ip if client_ip != "unknown" else session_id

    # Get dynamic settings from MongoDB (falls back to Settings defaults)
    dyn_config = await mongo_repo.get_dynamic_settings(settings)
    spam_limit = dyn_config.get("spam_limit", 10)
    block_hours = dyn_config.get("block_duration_hours", 48)
    rate_limit = dyn_config.get("rate_limit_requests", 30)
    rate_window = dyn_config.get("rate_limit_window_seconds", 60)

    # 1. Check if user is blocked
    is_blocked, blocked_until = await mongo_repo.is_user_blocked(user_key)
    if is_blocked:
        # Format block message
        blocked_str = blocked_until.strftime("%Y-%m-%d %H:%M:%S") if blocked_until else "N/A"
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User is temporarily blocked due to multiple safety violations. Blocked until: {blocked_str} UTC."
        )

    # 2. Check rate limit
    allowed = await mongo_repo.record_request_and_check_rate_limit(user_key, rate_limit, rate_window)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please try again later."
        )

    # 3. Check safety / spam content
    is_safe, reason = await safety_service.check_safety(query)
    if not is_safe:
        # Increment spam count in DB
        spam_count, is_blocked_now, blocked_until = await mongo_repo.increment_spam_count(
            user_key, spam_limit, block_hours
        )
        if is_blocked_now:
            blocked_str = blocked_until.strftime("%Y-%m-%d %H:%M:%S") if blocked_until else "N/A"
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"User has been temporarily blocked until {blocked_str} UTC "
                    f"({block_hours} hours) after exceeding safety limit of {spam_limit} messages."
                )
            )

        warning_msg = (
            f"I'm sorry, but your message has been flagged as unsafe/spam ({reason}). "
            f"Please write clean queries. Attempt {spam_count} of {spam_limit} before a {block_hours}-hour temporary block."
        )
        return False, warning_msg

    return True, ""


@router.post("/stream")
async def chat_stream(request: Request, body: ChatRequestSchema) -> StreamingResponse:
    """Stream an AI answer over Server-Sent Events (SSE)."""
    # Check rate limit, user block, and query safety
    is_safe, warning_msg = await check_user_safety_and_limits(request, body.query, body.session_id)
    if not is_safe:
        async def warning_stream() -> AsyncIterator[str]:
            yield _format_sse_event({"type": "token", "content": warning_msg})
            yield _format_sse_event({
                "type": "done",
                "query": body.query,
                "sources": [],
                "validation": {"safety_ok": False, "hallucination_flagged": False}
            })

        return StreamingResponse(
            warning_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    container = request.app.state.container

    async def event_stream() -> AsyncIterator[str]:
        async for event in container.chat_with_trips.stream_execute(
            ChatRequest(
                query=body.query,
                top_k=body.top_k,
                session_id=body.session_id
            )
        ):
            yield _format_sse_event(event)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/voice-input", response_model=VoiceChatResponseSchema)
async def voice_chat(
    request: Request,
    file: UploadFile | None = File(None),
    text_query: str | None = Form(None),
    session_id: str = Form("default_session"),
    top_k: int = Form(3),
    language: str = Form("hi-IN"),
) -> VoiceChatResponseSchema:
    """Transcribe audio with Whisper, run chat pipeline, generate TTS response and return combined JSON."""
    container = request.app.state.container
    
    # 1. Resolve transcription / text input
    if text_query:
        transcript = text_query
    elif file:
        audio_bytes = await file.read()
        try:
            transcript = await container.voice_service.transcribe_audio(audio_bytes, file.filename, language)
        except Exception as e:
            transcript = "hello"
            logger.error(f"Whisper transcription failed: {e}", exc_info=True)
    else:
        transcript = "hello"

    if not transcript:
        transcript = "hello"

    # Check rate limit, user block, and query safety
    is_safe, warning_msg = await check_user_safety_and_limits(request, transcript, session_id)
    if not is_safe:
        audio_base64 = None
        try:
            audio_bytes = await container.voice_service.generate_speech(warning_msg, language)
            audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")
        except Exception as e:
            logger.error(f"TTS generation for safety warning failed: {e}", exc_info=True)

        return VoiceChatResponseSchema(
            query=transcript,
            answer=warning_msg,
            intent="SMALL_TALK",
            entities={},
            sources=[],
            audio_base64=audio_base64,
            validation={"safety_ok": False, "hallucination_flagged": False}
        )

    # 3. Execute chat pipeline and aggregate stream events
    full_answer = ""
    sources = []
    intent = "SMALL_TALK"
    entities = {}
    validation = {"safety_ok": True, "hallucination_flagged": False}
    
    async for event in container.chat_with_trips.stream_execute(
        ChatRequest(query=transcript, top_k=top_k, session_id=session_id, voice_mode=True)
    ):
        event_type = event.get("type")
        if event_type == "metadata":
            intent = event.get("intent", "SMALL_TALK")
            entities = event.get("entities", {})
        elif event_type == "sources":
            sources = event.get("sources", [])
        elif event_type == "token":
            full_answer += event.get("content", "")
        elif event_type == "done":
            sources = event.get("sources", sources)
            validation = event.get("validation", validation)

    # 4. Generate TTS audio bytes
    audio_base64 = None
    if full_answer:
        try:
            # Strip markdown formatting out of spoken text
            speakable_text = (
                full_answer.replace("**", "")
                .replace("* ", "")
                .replace("- ", "")
                .replace("\n", " ")
                .strip()
            )
            
            # If it is the final generated itinerary, use a concise, natural voice prompt for TTS
            if intent == "ITINERARY" and "📅 **Trip Duration**" not in full_answer:
                dest_name = entities.get("destination") or "your destination"
                days_count = entities.get("duration_days") or 3
                speakable_text = (
                    f"I have created your customized {days_count}-day itinerary for {dest_name}! "
                    "I have listed the day-by-day schedule, recommended stays, food spots, and attractions on your screen. "
                    "Take a look at the details. Where would you like to start first?"
                )

            audio_bytes = await container.voice_service.generate_speech(speakable_text, language)
            audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")
        except Exception as e:
            logger.error(f"TTS generation failed: {e}", exc_info=True)

    return VoiceChatResponseSchema(
        query=transcript,
        answer=full_answer,
        intent=intent,
        entities=entities,
        sources=[
            TripSourceSchema(
                id=s["id"],
                title=s["title"],
                destination=s["destination"],
                score=s["score"]
            )
            for s in sources
        ],
        audio_base64=audio_base64,
        validation=validation
    )


@router.get("/tts")
async def get_tts(
    request: Request,
    text: str = Query(...),
) -> Response:
    """Generate and return text-to-speech raw audio stream."""
    container = request.app.state.container
    try:
        audio_bytes = await container.voice_service.generate_speech(text)
        return Response(content=audio_bytes, media_type="audio/mpeg")
    except Exception as e:
        return Response(content=str(e), status_code=500, media_type="text/plain")


@router.post("/clear")
def clear_history(
    request: Request,
    session_id: str = Query("default_session"),
) -> dict[str, str]:
    """Clear memory history for a session."""
    container = request.app.state.container
    container.memory_manager.clear_history(session_id)
    return {"status": "history cleared", "session_id": session_id}
