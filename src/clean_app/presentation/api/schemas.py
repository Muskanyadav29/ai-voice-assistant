"""Pydantic schemas for API requests and responses."""

from pydantic import BaseModel, Field


class ItineraryItemSchema(BaseModel):
    day: int
    title: str
    description: str
    activities: list[str]
    formatted_address: str


class TripSchema(BaseModel):
    id: str
    title: str
    destination: str
    country: str
    duration_days: int
    price: float
    currency: str
    description: str
    tags: list[str]
    start_date: str
    highlights: list[str]
    itinerary: list[ItineraryItemSchema]



class IndexTripsSchema(BaseModel):
    indexed_count: int
    total_in_store: int


class ChatRequestSchema(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(default=3, ge=1, le=10)
    session_id: str = Field(default="default_session")


class TripSourceSchema(BaseModel):
    id: str
    title: str
    destination: str
    score: float


class ChatResponseSchema(BaseModel):
    query: str
    answer: str
    sources: list[TripSourceSchema]
