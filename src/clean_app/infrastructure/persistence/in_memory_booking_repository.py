"""In-memory and JSON file-backed booking repository implementation."""

import json
from pathlib import Path
from clean_app.domain.entities.booking import Booking
from clean_app.domain.repositories.booking_repository import BookingRepository


class InMemoryBookingRepository(BookingRepository):
    """Stores bookings in memory and persists them to a JSON file."""

    def __init__(self, persist_file_path: str = "./data/bookings.json") -> None:
        self._file_path = Path(persist_file_path)
        self._bookings: dict[str, Booking] = {}
        self._load_from_file()

    def save(self, booking: Booking) -> None:
        self._bookings[booking.id] = booking
        self._save_to_file()

    def get_all(self) -> list[Booking]:
        return list(self._bookings.values())

    def get_by_id(self, booking_id: str) -> Booking | None:
        return self._bookings.get(booking_id)

    def _load_from_file(self) -> None:
        if not self._file_path.exists():
            return
        try:
            with open(self._file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for item in data:
                    booking = Booking(
                        id=item["id"],
                        trip_id=item["trip_id"],
                        trip_title=item["trip_title"],
                        customer_name=item["customer_name"],
                        booking_date=item["booking_date"],
                        price=float(item["price"]),
                        status=item.get("status", "Confirmed"),
                    )
                    self._bookings[booking.id] = booking
        except Exception as e:
            # Fallback/Log in case of file corruptions
            print(f"Error loading bookings from file: {e}")

    def _save_to_file(self) -> None:
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            data = []
            for b in self._bookings.values():
                data.append({
                    "id": b.id,
                    "trip_id": b.trip_id,
                    "trip_title": b.trip_title,
                    "customer_name": b.customer_name,
                    "booking_date": b.booking_date,
                    "price": b.price,
                    "status": b.status,
                })
            with open(self._file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving bookings to file: {e}")
