"""Structured Itinerary Planning API Router."""

from typing import Any
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from clean_app.application.use_cases.plan_itinerary import ItineraryPlanRequest

router = APIRouter(prefix="/itinerary", tags=["itinerary"])


class ItineraryPlanSchema(BaseModel):
    destination: str = Field(..., description="Target destination city or region in India.")
    duration_days: int = Field(3, ge=1, le=14, description="Trip duration in days (1-14).")
    budget_level: str = Field("moderate", description="Budget tier: budget, moderate, luxury.")
    travel_style: str = Field("balanced", description="Vibe: adventure, relax, cultural, romantic, family.")
    interests: list[str] = Field(default_factory=list, description="Specific interests e.g. food, trekking, heritage.")
    companions: str = Field("solo", description="Travel group type: solo, couple, family, friends.")


class DayItinerarySchema(BaseModel):
    day: int
    title: str
    morning: str
    afternoon: str
    evening: str
    recommended_food: str
    stay_suggestion: str


class ItineraryResponseSchema(BaseModel):
    destination: str
    duration_days: int
    travel_style: str
    budget_estimate_inr: float
    summary: str
    days: list[DayItinerarySchema]
    matching_trips: list[dict[str, Any]]
    rag_context_snippets: list[str]


@router.post("/plan", response_model=ItineraryResponseSchema, status_code=status.HTTP_200_OK)
async def plan_itinerary(request: Request, body: ItineraryPlanSchema) -> ItineraryResponseSchema:
    """Generate a complete structured day-by-day itinerary plan combining trip catalog and RAG knowledge."""
    container = request.app.state.container
    try:
        req = ItineraryPlanRequest(
            destination=body.destination,
            duration_days=body.duration_days,
            budget_level=body.budget_level,
            travel_style=body.travel_style,
            interests=body.interests,
            companions=body.companions,
        )
        res = await container.plan_itinerary.execute(req)
        return ItineraryResponseSchema(
            destination=res.destination,
            duration_days=res.duration_days,
            travel_style=res.travel_style,
            budget_estimate_inr=res.budget_estimate_inr,
            summary=res.summary,
            days=[
                DayItinerarySchema(
                    day=d.day,
                    title=d.title,
                    morning=d.morning,
                    afternoon=d.afternoon,
                    evening=d.evening,
                    recommended_food=d.recommended_food,
                    stay_suggestion=d.stay_suggestion,
                )
                for d in res.days
            ],
            matching_trips=res.matching_trips,
            rag_context_snippets=res.rag_context_snippets,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while generating the itinerary: {e}",
        )
