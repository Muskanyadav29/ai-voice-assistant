"""Place details repository interface."""

from abc import ABC, abstractmethod
from clean_app.domain.entities.place_details import PlaceDetails


class PlaceDetailsRepository(ABC):
    """Port for loading and storing place details data."""

    @abstractmethod
    async def save(self, place_details: PlaceDetails) -> None:
        """Save place details to the repository."""

    @abstractmethod
    async def get_by_name(self, name: str) -> PlaceDetails | None:
        """Retrieve place details by name (case-insensitive)."""

    @abstractmethod
    async def get_all(self) -> list[PlaceDetails]:
        """Retrieve all stored place details."""

