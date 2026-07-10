"""Data transfer objects for trip operations."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ItineraryItemResponse:
    """DTO representing a single day's plan in a trip itinerary."""

    day: int
    title: str
    description: str
    activities: list[str]
    formatted_address: str


@dataclass(frozen=True, slots=True)
class TripResponse:
    """Output representing a trip."""

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
    itinerary: list[ItineraryItemResponse]



@dataclass(frozen=True, slots=True)
class IndexTripsResponse:
    """Output after indexing trips into the vector store."""

    indexed_count: int
    total_in_store: int


@dataclass(frozen=True, slots=True)
class TripSourceResponse:
    """A trip cited in a chat answer."""

    id: str
    title: str
    destination: str
    score: float


@dataclass(frozen=True, slots=True)
class ChatRequest:
    """Input for a trip-aware chat query."""

    query: str
    top_k: int = 3
    session_id: str = "default_session"
    voice_mode: bool = False


@dataclass(frozen=True, slots=True)
class ChatResponse:
    """AI chat response grounded in trip data."""

    query: str
    answer: str
    sources: list[TripSourceResponse]
