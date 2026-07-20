"""Use case for indexing MongoDB trip documents into the vector store."""

from dataclasses import dataclass
from clean_app.domain.repositories.trip_repository import TripRepository
from clean_app.domain.repositories.vector_store import VectorStore
from clean_app.infrastructure.persistence.mongo_trip_repository import MongoTripRepository


@dataclass(frozen=True, slots=True)
class IndexMongoTripsResult:
    indexed_count: int
    total_trips_in_store: int


class IndexMongoTripsUseCase:
    """Fetches trips from MongoDB repository and indexes them into the vector store."""

    def __init__(self, trip_repository: TripRepository, vector_store: VectorStore) -> None:
        self._trip_repository = trip_repository
        self._vector_store = vector_store

    async def execute(self) -> IndexMongoTripsResult:
        if isinstance(self._trip_repository, MongoTripRepository):
            trips = await self._trip_repository.get_all_async()
        else:
            trips = self._trip_repository.get_all()

        if trips:
            self._vector_store.add_trips(trips)

        return IndexMongoTripsResult(
            indexed_count=len(trips),
            total_trips_in_store=self._vector_store.count(),
        )
