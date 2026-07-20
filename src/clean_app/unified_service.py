"""Unified AI Service merging AI Chat, FAQ Training, PDF Training, Website Training, MongoDB Trips Training, and Itinerary Planning into 1 synchronous class & interface."""

import base64
from typing import Any
from clean_app.application.dto.trip_dto import ChatRequest
from clean_app.application.use_cases.ingest_faq import FaqItem
from clean_app.application.use_cases.plan_itinerary import ItineraryPlanRequest
from clean_app.presentation.api.dependencies import AppContainer, build_container


class UnifiedAIService:
    """Merged AI Service exposing 1 single Python & REST API interface for all AI operations."""

    def __init__(self, container: AppContainer | None = None) -> None:
        self.container = container or build_container()

    def train_faq(self, faqs: list[dict[str, str]]) -> dict[str, Any]:
        """Synchronously train and index FAQ questions & answers into vector store."""
        faq_objects = [
            FaqItem(
                question=item.get("question", ""),
                answer=item.get("answer", ""),
                category=item.get("category", "General")
            )
            for item in faqs
            if item.get("question") and item.get("answer")
        ]
        if not faq_objects:
            return {"status": "skipped", "message": "No valid FAQ items provided."}
        
        res = self.container.ingest_faq.execute(faq_objects)
        return {
            "status": "success",
            "added_count": res.added_count,
            "total_in_store": res.total_in_store,
            "sample_ids": res.sample_ids,
        }

    def train_pdf(self, filename: str, pdf_bytes: bytes) -> dict[str, Any]:
        """Synchronously train and index an uploaded PDF document into vector store."""
        res = self.container.ingest_pdf.execute(filename, pdf_bytes)
        return {
            "status": "success",
            "id": res.id,
            "title": res.title,
            "url": res.url,
            "char_count": res.char_count,
            "total_in_store": res.total_in_store,
        }

    def train_pdf_base64(self, filename: str, pdf_base64: str) -> dict[str, Any]:
        """Synchronously train on a Base64-encoded PDF string."""
        raw_bytes = base64.b64decode(pdf_base64)
        return self.train_pdf(filename, raw_bytes)

    async def train_website(self, url: str) -> dict[str, Any]:
        """Synchronously download, extract, and index a website URL into vector store."""
        res = await self.container.ingest_website.execute(url)
        return {
            "status": "success",
            "id": res.id,
            "title": res.title,
            "url": res.url,
            "char_count": res.char_count,
            "total_in_store": res.total_in_store,
        }

    async def train_mongodb_trips(self) -> dict[str, Any]:
        """Synchronously fetch live MongoDB trip documents and index them into vector store."""
        res = await self.container.index_mongo_trips.execute()
        return {
            "status": "success",
            "indexed_count": res.indexed_count,
            "total_trips_in_store": res.total_trips_in_store,
        }

    async def chat(self, query: str, session_id: str = "default_session", top_k: int = 3) -> dict[str, Any]:
        """Synchronously process AI chat query with multi-source RAG (Mongo trips, FAQ, PDF, Web)."""
        full_answer = ""
        sources = []
        intent = "SMALL_TALK"
        entities = {}
        validation = {"safety_ok": True, "hallucination_flagged": False}

        async for event in self.container.chat_with_trips.stream_execute(
            ChatRequest(query=query, top_k=top_k, session_id=session_id)
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

        return {
            "query": query,
            "answer": full_answer,
            "intent": intent,
            "entities": entities,
            "sources": sources,
            "validation": validation,
        }

    async def plan_itinerary(
        self,
        destination: str,
        duration_days: int = 3,
        budget_level: str = "moderate",
        travel_style: str = "balanced",
        companions: str = "solo",
    ) -> dict[str, Any]:
        """Synchronously generate a complete structured day-by-day travel itinerary."""
        plan_req = ItineraryPlanRequest(
            destination=destination,
            duration_days=duration_days,
            budget_level=budget_level,
            travel_style=travel_style,
            companions=companions,
        )
        plan_res = await self.container.plan_itinerary.execute(plan_req)
        return {
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

    async def sync_all_in_one_row(
        self,
        faq_items: list[dict[str, str]] | None = None,
        website_url: str | None = None,
        pdf_filename: str | None = None,
        pdf_base64: str | None = None,
        sync_mongodb: bool = False,
        query: str | None = None,
        destination: str | None = None,
        duration_days: int = 3,
        session_id: str = "default_session",
    ) -> dict[str, Any]:
        """Execute FAQ training, PDF training, Website training, MongoDB training, AI Chat, and Itinerary in ONE single synchronous row."""
        summary: dict[str, Any] = {}

        # 1. Train FAQ
        if faq_items:
            summary["faq"] = self.train_faq(faq_items)

        # 2. Train PDF
        if pdf_filename and pdf_base64:
            summary["pdf"] = self.train_pdf_base64(pdf_filename, pdf_base64)

        # 3. Train Website
        if website_url:
            summary["website"] = await self.train_website(website_url)

        # 4. Train MongoDB Trips
        if sync_mongodb:
            summary["mongodb_trips"] = await self.train_mongodb_trips()

        # 5. AI Chat
        chat_res = None
        if query:
            chat_res = await self.chat(query, session_id=session_id)

        # 6. Itinerary Planning
        itinerary_res = None
        if destination:
            itinerary_res = await self.plan_itinerary(destination=destination, duration_days=duration_days)

        summary["total_vector_documents"] = self.container.vector_store.count_knowledge()
        summary["total_vector_trips"] = self.container.vector_store.count()

        return {
            "status": "success",
            "training_summary": summary,
            "chat_response": chat_res,
            "itinerary_response": itinerary_res,
        }
