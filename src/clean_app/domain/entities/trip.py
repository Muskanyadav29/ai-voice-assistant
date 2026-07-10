"""Trip domain entity."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ItineraryItem:
    """Represents a single day's plan in a trip itinerary."""

    day: int
    title: str
    description: str
    activities: tuple[str, ...]
    formatted_address: str

    def to_text(self) -> str:
        """Convert to plain text representation."""
        act_text = ", ".join(self.activities)
        addr = f" at {self.formatted_address}" if self.formatted_address else ""
        return f"Day {self.day}: {self.title}. {self.description} Activities: {act_text}{addr}."


@dataclass(frozen=True, slots=True)
class Trip:
    """Represents a travel trip offering."""

    id: str
    title: str
    destination: str
    country: str
    duration_days: int
    price: float
    currency: str
    description: str
    tags: tuple[str, ...]
    start_date: str
    highlights: tuple[str, ...]
    itinerary: tuple[ItineraryItem, ...]

    def to_search_text(self) -> str:
        """Build a text representation used for vector embedding."""
        tag_text = ", ".join(self.tags)
        highlight_text = ", ".join(self.highlights)
        price_label = f"{self.currency} {self.price:.0f}"
        itinerary_text = " ".join(item.to_text() for item in self.itinerary)
        
        return (
            f"Title: {self.title}. "
            f"Destination: {self.destination}, {self.country}. "
            f"Duration: {self.duration_days} days. "
            f"Price: {price_label}. "
            f"Season: {self.start_date}. "
            f"Tags: {tag_text}. "
            f"Highlights: {highlight_text}. "
            f"Description: {self.description}. "
            f"Itinerary: {itinerary_text}"
        )

