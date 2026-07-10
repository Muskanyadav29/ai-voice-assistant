"""Booking domain entity."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Booking:
    """Represents a customer booking of a travel trip."""

    id: str
    trip_id: str
    trip_title: str
    customer_name: str
    booking_date: str  # ISO format string (e.g. YYYY-MM-DD)
    price: float
    status: str = "Confirmed"
