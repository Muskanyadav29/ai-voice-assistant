"""Use case for generating comprehensive structured travel itineraries."""

from dataclasses import dataclass, field
from typing import Any

from clean_app.domain.repositories.trip_repository import TripRepository
from clean_app.domain.repositories.vector_store import VectorStore


@dataclass
class ItineraryPlanRequest:
    destination: str
    duration_days: int = 3
    budget_level: str = "moderate"  # budget, moderate, luxury
    travel_style: str = "balanced"  # adventure, relaxation, cultural, romantic, family
    interests: list[str] = field(default_factory=list)
    companions: str = "solo"


@dataclass
class DayItinerary:
    day: int
    title: str
    morning: str
    afternoon: str
    evening: str
    recommended_food: str
    stay_suggestion: str


@dataclass
class ItineraryPlanResponse:
    destination: str
    duration_days: int
    travel_style: str
    budget_estimate_inr: float
    summary: str
    days: list[DayItinerary]
    matching_trips: list[dict[str, Any]]
    rag_context_snippets: list[str]


class PlanItineraryUseCase:
    """Generates structured day-by-day itineraries using RAG knowledge, trip catalog, and static rules."""

    def __init__(
        self,
        trip_repo: TripRepository,
        vector_store: VectorStore,
        static_itinerary_engine: Any = None,
        google_places_service: Any = None,
    ) -> None:
        self._trip_repo = trip_repo
        self._vector_store = vector_store
        self._static_engine = static_itinerary_engine
        self._google_places = google_places_service

    async def execute(self, request: ItineraryPlanRequest) -> ItineraryPlanResponse:
        dest = request.destination.strip().title()
        days_count = max(1, min(14, request.duration_days))

        # 1. Search trip catalog
        catalog_trips = self._trip_repo.get_all()
        matching_trips = [
            {
                "id": t.id,
                "title": t.title,
                "destination": t.destination,
                "duration_days": t.duration_days,
                "price": t.price,
                "currency": t.currency,
            }
            for t in catalog_trips
            if dest.lower() in t.destination.lower() or dest.lower() in t.title.lower()
        ]

        # 2. Search vector store RAG
        rag_snippets: list[str] = []
        try:
            vector_results = self._vector_store.search_knowledge(f"{dest} itinerary places travel guide", top_k=3)
            rag_snippets = [r.content[:300] + "..." for r in vector_results]
        except Exception:
            pass

        # 3. Generate Day-by-Day schedule
        days_schedule: list[DayItinerary] = []
        multiplier = 2500 if request.budget_level == "budget" else (5500 if request.budget_level == "moderate" else 12000)
        total_budget = days_count * multiplier

        for d in range(1, days_count + 1):
            if d == 1:
                title = f"Day 1: Arrival & {dest} City Overview"
                morning = f"Arrive in {dest}, check in to hotel, and unpack."
                afternoon = f"Explore central market and iconic landmarks in {dest}."
                evening = f"Sunset view at local viewpoint followed by evening walk."
                food = "Local street food specialties and traditional thali dinner."
                stay = f"Centrally located 3-star/4-star hotel near {dest} city center."
            elif d == days_count:
                title = f"Day {d}: Farewell & Souvenir Shopping"
                morning = f"Leisurely breakfast and souvenir shopping at traditional bazaar."
                afternoon = f"Visit last-minute cultural spots and enjoy a quiet lunch."
                evening = f"Check-out and departure from {dest} with great memories."
                food = "Popular café lunch and regional sweets."
                stay = "N/A (Departure Day)"
            else:
                title = f"Day {d}: Deep Dive into {dest} Culture & Attractions"
                morning = f"Morning guided visit to top historical or natural attractions."
                afternoon = f"Scenic outdoor activities, photo stops, and local lunch."
                evening = f"Cultural performance or relaxing evening cafe hop."
                food = "Top-rated local specialty restaurant."
                stay = f"Comfortable boutique stay in {dest}."

            days_schedule.append(
                DayItinerary(
                    day=d,
                    title=title,
                    morning=morning,
                    afternoon=afternoon,
                    evening=evening,
                    recommended_food=food,
                    stay_suggestion=stay,
                )
            )

        summary = (
            f"Here is your customized {days_count}-day {request.travel_style} itinerary for {dest} "
            f"with a {request.budget_level} budget preference. Tailored for {request.companions} travel."
        )

        return ItineraryPlanResponse(
            destination=dest,
            duration_days=days_count,
            travel_style=request.travel_style,
            budget_estimate_inr=float(total_budget),
            summary=summary,
            days=days_schedule,
            matching_trips=matching_trips,
            rag_context_snippets=rag_snippets,
        )
