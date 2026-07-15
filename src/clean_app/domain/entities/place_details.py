"""Place details domain entity."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class PlaceDetails:
    """Represents structured information about a country, state, or city."""

    name: str
    place_type: str  # "country", "state", "city"
    description: str
    capital: str | None = None
    currency: str | None = None
    languages: list[str] = field(default_factory=list)
    population: str | None = None
    climate: str | None = None
    tourist_places: list[str] = field(default_factory=list)
    popular_foods: list[str] = field(default_factory=list)
    festivals: list[str] = field(default_factory=list)
    history: str | None = None
    parent_region: str | None = None  # e.g. "India" for Maharashtra, "Maharashtra" for Mumbai
    additional_info: dict[str, Any] = field(default_factory=dict)
