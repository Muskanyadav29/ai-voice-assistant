"""MongoDB implementation of TripRepository with local JSON fallback."""

import json
from pathlib import Path
from typing import Any

from clean_app.domain.entities.trip import Trip, ItineraryItem
from clean_app.domain.repositories.trip_repository import TripRepository
from clean_app.infrastructure.config.settings import Settings

try:
    from motor.motor_asyncio import AsyncIOMotorClient
    MOTOR_AVAILABLE = True
except ImportError:
    MOTOR_AVAILABLE = False

DEFAULT_TRIPS_FILE = Path(__file__).resolve().parent.parent.parent.parent / "data" / "cached_trips.json"
FALLBACK_TRIPS_FILE = Path(__file__).resolve().parent.parent.parent.parent / "data" / "trips.json"


class MongoTripRepository(TripRepository):
    """Trip repository backing trip data in MongoDB with persistent JSON fallback."""

    def __init__(self, settings: Settings, trips_file: Path | None = None) -> None:
        self._trips_file = trips_file or (DEFAULT_TRIPS_FILE if DEFAULT_TRIPS_FILE.exists() else FALLBACK_TRIPS_FILE)
        self._mem_trips: list[Trip] = self._load_local_trips()

        self._enabled = MOTOR_AVAILABLE
        if self._enabled:
            try:
                self._client = AsyncIOMotorClient(
                    settings.mongodb_uri,
                    serverSelectionTimeoutMS=2000,
                    connectTimeoutMS=2000
                )
                self._db = self._client[settings.mongodb_db_name]
                self._collection = self._db["trips"]
            except Exception as e:
                print(f"Failed to initialize MongoDB client for trips: {e}. Falling back to local trips.")
                self._enabled = False

    def _load_local_trips(self) -> list[Trip]:
        if not self._trips_file.exists():
            return []
        try:
            raw = json.loads(self._trips_file.read_text(encoding="utf-8"))
            return [self._raw_to_trip(item) for item in raw]
        except Exception as e:
            print(f"Error loading local trips: {e}")
            return []

    def _raw_to_trip(self, item: dict[str, Any]) -> Trip:
        return Trip(
            id=str(item.get("id") or item.get("_id") or "trip_unknown"),
            title=item.get("title", "Untitled Trip"),
            destination=item.get("destination", "India"),
            country=item.get("country", "India"),
            duration_days=int(item.get("duration_days", item.get("days", 3))),
            price=float(item.get("price", item.get("price_inr", item.get("price_usd", 0)))),
            currency=str(item.get("currency", "INR")),
            description=item.get("description", ""),
            tags=tuple(item.get("tags", [])),
            start_date=item.get("start_date", "2026-10-01"),
            highlights=tuple(item.get("highlights", [])),
            itinerary=tuple([
                ItineraryItem(
                    day=it.get("day", i + 1),
                    title=it.get("title", f"Day {i + 1}"),
                    activities=it.get("activities", "") if isinstance(it.get("activities"), str) else ", ".join(it.get("activities", []))
                )
                for i, it in enumerate(item.get("itinerary", []))
            ]),
        )

    def _trip_to_doc(self, trip: Trip) -> dict[str, Any]:
        return {
            "_id": trip.id,
            "id": trip.id,
            "title": trip.title,
            "destination": trip.destination,
            "country": trip.country,
            "duration_days": trip.duration_days,
            "price": trip.price,
            "currency": trip.currency,
            "description": trip.description,
            "tags": list(trip.tags),
            "start_date": trip.start_date,
            "highlights": list(trip.highlights),
            "itinerary": [
                {"day": it.day, "title": it.title, "activities": it.activities}
                for it in trip.itinerary
            ],
        }

    def get_all(self) -> list[Trip]:
        """Synchronous get_all using in-memory / fallback trips cache."""
        return list(self._mem_trips)

    def get_by_id(self, trip_id: str) -> Trip | None:
        for trip in self._mem_trips:
            if trip.id == trip_id:
                return trip
        return None

    async def get_all_async(self) -> list[Trip]:
        """Fetch all trips from MongoDB if available, else in-memory cache."""
        if not self._enabled:
            return self.get_all()

        try:
            cursor = self._collection.find({})
            docs = await cursor.to_list(length=500)
            if docs:
                trips = [self._raw_to_trip(doc) for doc in docs]
                self._mem_trips = trips
                return trips
        except Exception as e:
            print(f"MongoDB fetch failed: {e}. Using local cache.")

        return self.get_all()

    async def save_trips_bulk(self, trips: list[Trip]) -> int:
        """Upsert a list of trips into MongoDB and update memory cache."""
        self._mem_trips = trips
        count = 0
        if not self._enabled:
            return len(trips)

        try:
            for trip in trips:
                doc = self._trip_to_doc(trip)
                await self._collection.update_one(
                    {"_id": trip.id},
                    {"$set": doc},
                    upsert=True
                )
                count += 1
            return count
        except Exception as e:
            print(f"Failed to bulk save trips to MongoDB: {e}")
            return len(trips)
