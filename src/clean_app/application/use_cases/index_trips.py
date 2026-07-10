"""Index trips into the vector store."""

from clean_app.application.dto.trip_dto import IndexTripsResponse
from clean_app.domain.repositories.trip_repository import TripRepository
from clean_app.domain.repositories.vector_store import VectorStore


class IndexTripsUseCase:
    """Load trips and embed them for semantic search."""

    def __init__(
        self,
        trip_repository: TripRepository,
        vector_store: VectorStore,
    ) -> None:
        self._trip_repository = trip_repository
        self._vector_store = vector_store

    def execute(self) -> IndexTripsResponse:
        trips = self._trip_repository.get_all()
        indexed_count = self._vector_store.index_trips(trips)
        return IndexTripsResponse(
            indexed_count=indexed_count,
            total_in_store=self._vector_store.count(),
        )
