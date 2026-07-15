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


class PlaceRequestSchema(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="The name of the country, state, or city.")


class PlaceDetailsResponseSchema(BaseModel):
    name: str
    place_type: str
    description: str
    capital: str | None = None
    currency: str | None = None
    languages: list[str] = Field(default_factory=list)
    population: str | None = None
    climate: str | None = None
    tourist_places: list[str] = Field(default_factory=list)
    popular_foods: list[str] = Field(default_factory=list)
    festivals: list[str] = Field(default_factory=list)
    history: str | None = None
    parent_region: str | None = None
    additional_info: dict[str, str | None] = Field(default_factory=dict)


