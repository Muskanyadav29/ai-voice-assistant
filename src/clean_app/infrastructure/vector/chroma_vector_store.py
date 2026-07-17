"""ChromaDB-backed vector store for trip semantic search."""

from __future__ import annotations

import json
from typing import Any

import chromadb
from chromadb.api.models.Collection import Collection

from clean_app.domain.entities.trip import ItineraryItem, Trip
from clean_app.domain.entities.knowledge import KnowledgeDocument
from clean_app.domain.repositories.vector_store import TripSearchResult, KnowledgeSearchResult, VectorStore

COLLECTION_NAME = "trips"
COLLECTION_KNOWLEDGE_NAME = "platform_knowledge"


class ChromaVectorStore(VectorStore):
    """Persist trip and knowledge embeddings using ChromaDB."""

    def __init__(self, persist_directory: str) -> None:
        self._fallback_mode = False
        self._trips_db: dict[str, Trip] = {}
        self._knowledge_db: dict[str, KnowledgeDocument] = {}
        try:
            self._client = chromadb.PersistentClient(path=persist_directory)
            self._collection: Collection = self._client.get_or_create_collection(
                name=COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
            self._knowledge_collection: Collection = self._client.get_or_create_collection(
                name=COLLECTION_KNOWLEDGE_NAME,
                metadata={"hnsw:space": "cosine"},
            )
        except (Exception, BaseException) as e:
            print(f"WARNING: Failed to initialize Chroma PersistentClient ({e}). Falling back to in-memory Python vector store.")
            self._fallback_mode = True

    def index_trips(self, trips: list[Trip]) -> int:
        if not trips:
            return 0

        if self._fallback_mode:
            newly_added = 0
            incoming_ids = {trip.id for trip in trips}
            for tid in list(self._trips_db.keys()):
                if tid not in incoming_ids:
                    del self._trips_db[tid]
            for trip in trips:
                if trip.id not in self._trips_db:
                    newly_added += 1
                self._trips_db[trip.id] = trip
            return newly_added

        existing = set(self._collection.get()["ids"])
        new_ids = {trip.id for trip in trips}

        # Delete any existing trips that are not in the new trips list
        to_delete = list(existing - new_ids)
        if to_delete:
            self._collection.delete(ids=to_delete)

        # Count how many of the incoming trips are new
        newly_added = [trip for trip in trips if trip.id not in existing]

        self._collection.upsert(
            ids=[trip.id for trip in trips],
            documents=[trip.to_search_text() for trip in trips],
            metadatas=[self._trip_to_metadata(trip) for trip in trips],
        )
        return len(newly_added)

    def search(self, query: str, top_k: int = 3) -> list[TripSearchResult]:
        if self.count() == 0:
            return []

        if self._fallback_mode:
            query_words = set(query.lower().split())
            results = []
            for trip in self._trips_db.values():
                search_text = trip.to_search_text().lower()
                matches = sum(1 for w in query_words if w in search_text)
                score = 0.5
                if query_words:
                    score = min(0.9, 0.5 + 0.4 * (matches / len(query_words)))
                if query.lower() in trip.destination.lower() or query.lower() in trip.title.lower():
                    score = 0.95
                results.append(TripSearchResult(trip=trip, score=score))
            results.sort(key=lambda r: r.score, reverse=True)
            return results[:top_k]

        result = self._collection.query(
            query_texts=[query],
            n_results=min(top_k, self.count()),
            include=["metadatas", "distances"],
        )

        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]

        matches: list[TripSearchResult] = []
        for metadata, distance in zip(metadatas, distances, strict=True):
            trip = self._metadata_to_trip(metadata)
            score = max(0.0, 1.0 - float(distance))
            matches.append(TripSearchResult(trip=trip, score=score))
        return matches

    def count(self) -> int:
        if self._fallback_mode:
            return len(self._trips_db)
        return int(self._collection.count())

    @staticmethod
    def _trip_to_metadata(trip: Trip) -> dict[str, Any]:
        itinerary_data = [
            {
                "day": item.day,
                "title": item.title,
                "description": item.description,
                "activities": list(item.activities),
                "formatted_address": item.formatted_address,
            }
            for item in trip.itinerary
        ]
        return {
            "id": trip.id,
            "title": trip.title,
            "destination": trip.destination,
            "country": trip.country,
            "duration_days": trip.duration_days,
            "price": trip.price,
            "currency": trip.currency,
            "description": trip.description,
            "tags": json.dumps(list(trip.tags)),
            "start_date": trip.start_date,
            "highlights": json.dumps(list(trip.highlights)),
            "itinerary": json.dumps(itinerary_data),
        }

    @staticmethod
    def _metadata_to_trip(metadata: dict[str, Any]) -> Trip:
        tags_raw = metadata.get("tags", "[]")
        tags = tuple(json.loads(tags_raw)) if isinstance(tags_raw, str) else tuple(tags_raw)

        highlights_raw = metadata.get("highlights", "[]")
        highlights = tuple(json.loads(highlights_raw)) if isinstance(highlights_raw, str) else tuple(highlights_raw)

        itinerary_raw = metadata.get("itinerary", "[]")
        itinerary_list = json.loads(itinerary_raw) if isinstance(itinerary_raw, str) else itinerary_raw
        itinerary_items = []
        if isinstance(itinerary_list, list):
            for item in itinerary_list:
                itinerary_items.append(
                    ItineraryItem(
                        day=int(item["day"]),
                        title=str(item["title"]),
                        description=str(item["description"]),
                        activities=tuple(item["activities"]),
                        formatted_address=str(item.get("formatted_address", "")),
                    )
                )

        return Trip(
            id=str(metadata["id"]),
            title=str(metadata["title"]),
            destination=str(metadata["destination"]),
            country=str(metadata["country"]),
            duration_days=int(metadata["duration_days"]),
            price=float(metadata.get("price", metadata.get("price_usd", 0))),
            currency=str(metadata.get("currency", "USD")),
            description=str(metadata["description"]),
            tags=tags,
            start_date=str(metadata["start_date"]),
            highlights=highlights,
            itinerary=tuple(itinerary_items),
        )

    def index_knowledge(self, documents: list[KnowledgeDocument]) -> int:
        if not documents:
            return 0

        if self._fallback_mode:
            newly_added = 0
            incoming_ids = {doc.id for doc in documents}
            for did in list(self._knowledge_db.keys()):
                if did not in incoming_ids:
                    del self._knowledge_db[did]
            for doc in documents:
                if doc.id not in self._knowledge_db:
                    newly_added += 1
                self._knowledge_db[doc.id] = doc
            return newly_added

        existing = set(self._knowledge_collection.get()["ids"])
        new_ids = {doc.id for doc in documents}

        to_delete = list(existing - new_ids)
        if to_delete:
            self._knowledge_collection.delete(ids=to_delete)

        newly_added = [doc for doc in documents if doc.id not in existing]

        self._knowledge_collection.upsert(
            ids=[doc.id for doc in documents],
            documents=[doc.to_search_text() for doc in documents],
            metadatas=[self._knowledge_to_metadata(doc) for doc in documents],
        )
        return len(newly_added)

    def search_knowledge(self, query: str, top_k: int = 3) -> list[KnowledgeSearchResult]:
        if self.count_knowledge() == 0:
            return []

        if self._fallback_mode:
            query_words = set(query.lower().split())
            results = []
            for doc in self._knowledge_db.values():
                search_text = doc.to_search_text().lower()
                matches = sum(1 for w in query_words if w in search_text)
                score = 0.5
                if query_words:
                    score = min(0.9, 0.5 + 0.4 * (matches / len(query_words)))
                if query.lower() in doc.title.lower():
                    score = 0.95
                results.append(KnowledgeSearchResult(document=doc, score=score))
            results.sort(key=lambda r: r.score, reverse=True)
            return results[:top_k]

        result = self._knowledge_collection.query(
            query_texts=[query],
            n_results=min(top_k, self.count_knowledge()),
            include=["metadatas", "distances"],
        )

        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]

        matches: list[KnowledgeSearchResult] = []
        for metadata, distance in zip(metadatas, distances, strict=True):
            doc = self._metadata_to_knowledge(metadata)
            score = max(0.0, 1.0 - float(distance))
            matches.append(KnowledgeSearchResult(document=doc, score=score))
        return matches

    def count_knowledge(self) -> int:
        if self._fallback_mode:
            return len(self._knowledge_db)
        return int(self._knowledge_collection.count())

    def add_knowledge_documents(self, documents: list[KnowledgeDocument]) -> int:
        if not documents:
            return 0

        if self._fallback_mode:
            newly_added = 0
            for doc in documents:
                if doc.id not in self._knowledge_db:
                    newly_added += 1
                self._knowledge_db[doc.id] = doc
            return newly_added

        existing = set(self._knowledge_collection.get()["ids"])
        newly_added = [doc for doc in documents if doc.id not in existing]

        self._knowledge_collection.upsert(
            ids=[doc.id for doc in documents],
            documents=[doc.to_search_text() for doc in documents],
            metadatas=[self._knowledge_to_metadata(doc) for doc in documents],
        )
        return len(newly_added)

    @staticmethod
    def _knowledge_to_metadata(doc: KnowledgeDocument) -> dict[str, Any]:
        return {
            "id": doc.id,
            "title": doc.title,
            "url": doc.url,
            "content": doc.content,
        }

    @staticmethod
    def _metadata_to_knowledge(metadata: dict[str, Any]) -> KnowledgeDocument:
        return KnowledgeDocument(
            id=str(metadata["id"]),
            title=str(metadata["title"]),
            url=str(metadata["url"]),
            content=str(metadata["content"]),
        )


