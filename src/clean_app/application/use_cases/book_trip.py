"""Book trip use case."""

import datetime
import random
from clean_app.domain.entities.booking import Booking
from clean_app.domain.repositories.booking_repository import BookingRepository
from clean_app.domain.repositories.trip_repository import TripRepository


class BookTripUseCase:
    """Use case to handle booking a travel package for a customer."""

    def __init__(self, booking_repo: BookingRepository, trip_repo: TripRepository) -> None:
        self._booking_repo = booking_repo
        self._trip_repo = trip_repo

    def execute(self, trip_id: str, customer_name: str = "Valued Customer") -> Booking:
        """Create a booking for a specific trip, generating a unique booking code."""
        trip = self._trip_repo.get_by_id(trip_id)
        if not trip:
            raise ValueError(f"Trip with ID '{trip_id}' not found in the catalog.")

        # Generate a unique Booking ID (e.g., TRV-12345)
        booking_num = random.randint(10000, 99999)
        booking_id = f"TRV-{booking_num}"

        # Current date in ISO format
        today_str = datetime.date.today().isoformat()

        booking = Booking(
            id=booking_id,
            trip_id=trip.id,
            trip_title=trip.title,
            customer_name=customer_name,
            booking_date=today_str,
            price=trip.price,
            status="Confirmed",
        )

        self._booking_repo.save(booking)
        return booking
