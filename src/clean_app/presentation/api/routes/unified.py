"""Unified 1-API Router providing single-endpoint synchronous execution for AI Chat, FAQ Training, PDF Training, Website Training, MongoDB Trips Training, and Itinerary Planning."""

import base64
from typing import Any
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field, HttpUrl

from clean_app.application.dto.trip_dto import ChatRequest
from clean_app.application.use_cases.ingest_faq import FaqItem
from clean_app.application.use_cases.plan_itinerary import ItineraryPlanRequest
from clean_app.presentation.api.schemas import FaqItemSchema, TripSourceSchema

router = APIRouter(prefix="/unified", tags=["unified"])


class UnifiedRequestSchema(BaseModel):
    action: str = Field(
        default="sync_all",
        description="Mode of operation: 'sync_all' (trains and chats in 1 row), 'chat', 'train_faq', 'train_pdf', 'train_website', 'train_mongodb', or 'itinerary'."
    )

    # 1. AI Chat query
    query: str | None = Field(default=None, description="User query for AI Chat.")
    session_id: str = Field(default="default_session", description="Session ID for chat memory.")

    # 2. FAQ Training items (Explicit Pydantic Model)
    faq_items: list[FaqItemSchema] | None = Field(
        default=None,
        description="List of FAQ objects with explicit 'question' and 'answer' fields."
    )

    # 3. PDF Training file
    pdf_base64: str | None = Field(default=None, description="Base64 encoded PDF bytes for document training.")
    pdf_filename: str = Field(default="document.pdf", description="Filename for PDF document.")

    # 4. Website Training URL
    website_url: HttpUrl | str | None = Field(default=None, description="Website URL to download and train on.")

    # 5. MongoDB Trips Training flag
    sync_mongodb: bool = Field(default=False, description="Set to True to trigger MongoDB trips indexing.")

    # 6. Itinerary Planning parameters
    destination: str | None = Field(default=None, description="Destination for structured itinerary planning.")
    duration_days: int = Field(default=3, ge=1, le=14, description="Duration in days (1-14).")
    budget_level: str = Field(default="moderate", description="Budget tier: budget, moderate, luxury.")
    travel_style: str = Field(default="balanced", description="Style: adventure, relax, cultural, romantic, family.")


class UnifiedResponseSchema(BaseModel):
    status: str
    action_performed: str
    training_summary: dict[str, Any] = Field(default_factory=dict)
    chat_response: dict[str, Any] | None = None
    itinerary_response: dict[str, Any] | None = None


@router.post("", response_model=UnifiedResponseSchema, status_code=status.HTTP_200_OK)
@router.post("/", response_model=UnifiedResponseSchema, status_code=status.HTTP_200_OK)
async def unified_api_handler(request: Request, body: UnifiedRequestSchema) -> UnifiedResponseSchema:
    """1 Single API Endpoint handling synchronous AI Chat, FAQ Training, PDF Training, Website Training, MongoDB Trips Training, and Itinerary Planning in one row."""
    container = request.app.state.container
    training_summary: dict[str, Any] = {}
    chat_out: dict[str, Any] | None = None
    itinerary_out: dict[str, Any] | None = None

    act = body.action.lower()

    # --- STEP 1: Process FAQ Training if provided or requested ---
    if body.faq_items or act in ("train_faq", "sync_all"):
        if body.faq_items:
            try:
                faq_objects = [
                    FaqItem(
                        question=item.question,
                        answer=item.answer,
                        category=item.category
                    )
                    for item in body.faq_items
                    if item.question and item.answer
                ]
                if faq_objects:
                    res_faq = container.ingest_faq.execute(faq_objects)
                    training_summary["faq"] = {
                        "status": "success",
                        "added_count": res_faq.added_count,
                        "sample_ids": res_faq.sample_ids
                    }
            except Exception as e:
                training_summary["faq"] = {"status": "error", "error": str(e)}

    # --- STEP 2: Process PDF Training if provided or requested ---
    if body.pdf_base64 or act in ("train_pdf", "sync_all"):
        if body.pdf_base64:
            try:
                raw_bytes = base64.b64decode(body.pdf_base64)
                res_pdf = container.ingest_pdf.execute(body.pdf_filename, raw_bytes)
                training_summary["pdf"] = {
                    "status": "success",
                    "title": res_pdf.title,
                    "char_count": res_pdf.char_count,
                    "id": res_pdf.id
                }
            except Exception as e:
                training_summary["pdf"] = {"status": "error", "error": str(e)}

    # --- STEP 3: Process Website Training if provided or requested ---
    if body.website_url or act in ("train_website", "sync_all"):
        if body.website_url:
            try:
                url_str = str(body.website_url)
                res_web = await container.ingest_website.execute(url_str)
                training_summary["website"] = {
                    "status": "success",
                    "title": res_web.title,
                    "url": res_web.url,
                    "char_count": res_web.char_count
                }
            except Exception as e:
                training_summary["website"] = {"status": "error", "error": str(e)}

    # --- STEP 4: Process MongoDB Trips Training if requested ---
    if body.sync_mongodb or act in ("train_mongodb", "sync_all"):
        if body.sync_mongodb or act == "train_mongodb":
            try:
                res_mongo = await container.index_mongo_trips.execute()
                training_summary["mongodb_trips"] = {
                    "status": "success",
                    "indexed_count": res_mongo.indexed_count,
                    "total_trips": res_mongo.total_trips_in_store
                }
            except Exception as e:
                training_summary["mongodb_trips"] = {"status": "error", "error": str(e)}

    # --- STEP 5: Process AI Chat if query provided or requested ---
    if body.query or act in ("chat", "sync_all"):
        q = body.query or (f"Tell me about travel in {body.destination}" if body.destination else "What trips are available?")
        full_answer = ""
        sources = []
        intent = "SMALL_TALK"
        entities = {}
        validation = {"safety_ok": True, "hallucination_flagged": False}

        try:
            async for event in container.chat_with_trips.stream_execute(
                ChatRequest(query=q, top_k=3, session_id=body.session_id)
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

            chat_out = {
                "query": q,
                "answer": full_answer,
                "intent": intent,
                "entities": entities,
                "sources": [
                    {
                        "id": s["id"],
                        "title": s["title"],
                        "destination": s.get("destination", ""),
                        "score": s.get("score", 0.0)
                    }
                    for s in sources
                ],
                "validation": validation
            }
        except Exception as e:
            chat_out = {"query": q, "error": str(e)}

    # --- STEP 6: Process Itinerary Planning if destination provided or requested ---
    if body.destination or act in ("itinerary", "sync_all"):
        if body.destination:
            try:
                plan_req = ItineraryPlanRequest(
                    destination=body.destination,
                    duration_days=body.duration_days,
                    budget_level=body.budget_level,
                    travel_style=body.travel_style,
                )
                plan_res = await container.plan_itinerary.execute(plan_req)
                itinerary_out = {
                    "destination": plan_res.destination,
                    "duration_days": plan_res.duration_days,
                    "travel_style": plan_res.travel_style,
                    "budget_estimate_inr": plan_res.budget_estimate_inr,
                    "summary": plan_res.summary,
                    "days": [
                        {
                            "day": d.day,
                            "title": d.title,
                            "morning": d.morning,
                            "afternoon": d.afternoon,
                            "evening": d.evening,
                            "recommended_food": d.recommended_food,
                            "stay_suggestion": d.stay_suggestion,
                        }
                        for d in plan_res.days
                    ],
                    "matching_trips": plan_res.matching_trips,
                    "rag_context_snippets": plan_res.rag_context_snippets,
                }
            except Exception as e:
                itinerary_out = {"destination": body.destination, "error": str(e)}

    # Overall vector store count
    training_summary["total_vector_documents"] = container.vector_store.count_knowledge()
    training_summary["total_vector_trips"] = container.vector_store.count()

    return UnifiedResponseSchema(
        status="success",
        action_performed=act,
        training_summary=training_summary,
        chat_response=chat_out,
        itinerary_response=itinerary_out,
    )
