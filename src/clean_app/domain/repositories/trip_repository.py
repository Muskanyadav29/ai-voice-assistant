"""Trip repository interface."""

from abc import ABC, abstractmethod

from clean_app.domain.entities.trip import Trip


class TripRepository(ABC):
    """Port for loading trip data."""

    @abstractmethod
    def get_all(self) -> list[Trip]:
        """Return all available trips."""

    @abstractmethod
    def get_by_id(self, trip_id: str) -> Trip | None:
        """Return a trip by identifier."""
