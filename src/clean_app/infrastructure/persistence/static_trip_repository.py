"""Load trips from a static JSON file."""

import json
from pathlib import Path

from clean_app.domain.entities.trip import ItineraryItem, Trip
from clean_app.domain.repositories.trip_repository import TripRepository

DEFAULT_TRIPS_FILE = Path(__file__).resolve().parent.parent / "data" / "trips.json"


class StaticTripRepository(TripRepository):
    """Trip repository backed by a local JSON file."""

    def __init__(self, trips_file: Path | None = None) -> None:
        self._trips_file = trips_file or DEFAULT_TRIPS_FILE
        self._trips = self._load_trips()

    def _load_trips(self) -> list[Trip]:
        raw = json.loads(self._trips_file.read_text(encoding="utf-8"))
        return [
            Trip(
                id=item["id"],
                title=item["title"],
                destination=item["destination"],
                country=item["country"],
                duration_days=int(item["duration_days"]),
                price=float(item.get("price", item.get("price_usd", 0))),
                currency=str(item.get("currency", "USD")),
                description=item["description"],
                tags=tuple(item["tags"]),
                start_date=item["start_date"],
                highlights=(),
                itinerary=(),
            )
            for item in raw
        ]


    def get_all(self) -> list[Trip]:
        return list(self._trips)

    def get_by_id(self, trip_id: str) -> Trip | None:
        for trip in self._trips:
            if trip.id == trip_id:
                return trip
        return None
