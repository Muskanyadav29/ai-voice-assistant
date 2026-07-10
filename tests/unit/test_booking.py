"""Unit tests for the booking system."""

from unittest.mock import MagicMock
import pytest
from clean_app.domain.entities.booking import Booking
from clean_app.domain.entities.trip import Trip
from clean_app.domain.repositories.trip_repository import TripRepository
from clean_app.infrastructure.persistence.in_memory_booking_repository import InMemoryBookingRepository
from clean_app.application.use_cases.book_trip import BookTripUseCase


def test_booking_entity_creation() -> None:
    booking = Booking(
        id="TRV-99999",
        trip_id="trip-123",
        trip_title="Swiss Alps Expedition",
        customer_name="John Doe",
        booking_date="2026-07-03",
        price=45000.0,
    )
    assert booking.id == "TRV-99999"
    assert booking.status == "Confirmed"
    assert booking.price == 45000.0


def test_in_memory_booking_repository(tmp_path) -> None:
    # Use a temp directory for JSON persistence to keep workspace clean during testing
    temp_json = tmp_path / "bookings.json"
    repo = InMemoryBookingRepository(persist_file_path=str(temp_json))
    
    assert len(repo.get_all()) == 0

    booking = Booking(
        id="TRV-12345",
        trip_id="trip-001",
        trip_title="Desert Safari",
        customer_name="Alice Smith",
        booking_date="2026-07-03",
        price=12000.0,
    )
    repo.save(booking)

    assert len(repo.get_all()) == 1
    assert repo.get_by_id("TRV-12345") == booking


def test_book_trip_use_case(tmp_path) -> None:
    temp_json = tmp_path / "bookings.json"
    booking_repo = InMemoryBookingRepository(persist_file_path=str(temp_json))
    
    # Mock trip repo
    trip_repo = MagicMock(spec=TripRepository)
    mock_trip = Trip(
        id="trip-abc",
        title="Udaipur Heritage Tour",
        destination="Udaipur",
        country="India",
        duration_days=3,
        price=15000.0,
        currency="INR",
        description="Heritage and lakes.",
        tags=("heritage", "culture"),
        start_date="Year-round",
        highlights=(),
        itinerary=(),
    )
    trip_repo.get_by_id.return_value = mock_trip

    use_case = BookTripUseCase(booking_repo, trip_repo)
    booking = use_case.execute("trip-abc", "Jane Doe")

    assert booking.trip_title == "Udaipur Heritage Tour"
    assert booking.price == 15000.0
    assert booking.customer_name == "Jane Doe"
    assert len(booking_repo.get_all()) == 1
