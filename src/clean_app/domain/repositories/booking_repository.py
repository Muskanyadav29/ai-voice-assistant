"""Booking repository port."""

from abc import ABC, abstractmethod

from clean_app.domain.entities.booking import Booking


class BookingRepository(ABC):
    """Port for storing and retrieving bookings."""

    @abstractmethod
    def save(self, booking: Booking) -> None:
        """Save a booking entity."""

    @abstractmethod
    def get_all(self) -> list[Booking]:
        """Retrieve all bookings."""

    @abstractmethod
    def get_by_id(self, booking_id: str) -> Booking | None:
        """Retrieve a booking by its unique ID."""
