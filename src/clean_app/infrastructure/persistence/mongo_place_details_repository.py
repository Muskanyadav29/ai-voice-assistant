"""MongoDB repository for storing generated place details with an in-memory/JSON file fallback."""

import json
from pathlib import Path
from typing import Any
from dataclasses import asdict
from clean_app.domain.entities.place_details import PlaceDetails
from clean_app.domain.repositories.place_details_repository import PlaceDetailsRepository
from clean_app.infrastructure.config.settings import Settings

try:
    from motor.motor_asyncio import AsyncIOMotorClient
    MOTOR_AVAILABLE = True
except ImportError:
    MOTOR_AVAILABLE = False


class MongoPlaceDetailsRepository(PlaceDetailsRepository):
    """Manages place details persistence with persistent JSON-file fallback."""

    def __init__(self, settings: Settings) -> None:
        self._fallback_file = Path(".places_fallback_state.json")
        self._load_fallback_state()

        self._enabled = MOTOR_AVAILABLE
        if self._enabled:
            try:
                # 2.0s timeout to fail fast if MongoDB is not reachable
                self._client = AsyncIOMotorClient(
                    settings.mongodb_uri,
                    serverSelectionTimeoutMS=2000,
                    connectTimeoutMS=2000
                )
                self._db = self._client[settings.mongodb_db_name]
                self._collection = self._db["places"]
            except Exception as e:
                print(f"Failed to initialize MongoDB client for places: {e}. Falling back to in-memory.")
                self._enabled = False

        if not self._enabled:
            print("WARNING: 'motor' not found or MongoDB unavailable. Falling back to local JSON state for places.")

    def _load_fallback_state(self) -> None:
        """Load local places fallback state from disk."""
        self._mem_db: dict[str, dict[str, Any]] = {}
        if not self._fallback_file.exists():
            return
        try:
            with open(self._fallback_file, "r", encoding="utf-8") as f:
                self._mem_db = json.load(f)
        except Exception as e:
            print(f"Failed to load places fallback state: {e}")

    def _save_fallback_state(self) -> None:
        """Save local places fallback state to disk."""
        try:
            with open(self._fallback_file, "w", encoding="utf-8") as f:
                json.dump(self._mem_db, f, indent=2)
        except Exception as e:
            print(f"Failed to save places fallback state: {e}")

    async def save(self, place_details: PlaceDetails) -> None:
        """Save place details to MongoDB or fallback JSON file."""
        data = asdict(place_details)
        name_key = place_details.name.lower().strip()

        if self._enabled:
            try:
                await self._collection.update_one(
                    {"name_lower": name_key},
                    {"$set": {**data, "name_lower": name_key}},
                    upsert=True
                )
                return
            except Exception as e:
                print(f"Failed to save place to MongoDB: {e}. Falling back to in-memory.")
                self._enabled = False

        self._mem_db[name_key] = data
        self._save_fallback_state()

    def _from_doc(self, doc: dict[str, Any]) -> PlaceDetails:
        """Deserialize database document to PlaceDetails domain entity."""
        return PlaceDetails(
            name=doc["name"],
            place_type=doc["place_type"],
            description=doc["description"],
            capital=doc.get("capital"),
            currency=doc.get("currency"),
            languages=doc.get("languages", []),
            population=doc.get("population"),
            climate=doc.get("climate"),
            tourist_places=doc.get("tourist_places") or doc.get("popular_places", []),
            popular_foods=doc.get("popular_foods", []),
            festivals=doc.get("festivals", []),
            history=doc.get("history"),
            parent_region=doc.get("parent_region"),
            additional_info=doc.get("additional_info", {})
        )

    async def get_by_name(self, name: str) -> PlaceDetails | None:
        """Retrieve place details by name (case-insensitive) from MongoDB or fallback JSON file."""
        name_key = name.lower().strip()

        if self._enabled:
            try:
                doc = await self._collection.find_one({"name_lower": name_key})
                if doc:
                    return self._from_doc(doc)
                return None
            except Exception as e:
                print(f"Failed to fetch place from MongoDB: {e}. Falling back to in-memory.")
                self._enabled = False

        doc = self._mem_db.get(name_key)
        if doc:
            return self._from_doc(doc)
        return None

    async def get_all(self) -> list[PlaceDetails]:
        """Retrieve all stored place details."""
        if self._enabled:
            try:
                cursor = self._collection.find()
                docs = await cursor.to_list(length=100)
                return [self._from_doc(doc) for doc in docs]
            except Exception as e:
                print(f"Failed to fetch all places from MongoDB: {e}. Falling back to in-memory.")
                self._enabled = False

        return [self._from_doc(doc) for doc in self._mem_db.values()]


