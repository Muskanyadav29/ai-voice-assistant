"""Unit tests for trip entity."""

from clean_app.domain.entities.trip import Trip


def test_trip_search_text_includes_key_fields() -> None:
    trip = Trip(
        id="trip-001",
        title="Paris City Break",
        destination="Paris",
        country="France",
        duration_days=5,
        price=1299,
        currency="USD",
        description="Explore museums and cafes.",
        tags=("city", "culture"),
        start_date="2026-09-10",
        highlights=("Eiffel Tower", "Louvre Museum"),
        itinerary=(),
    )
    text = trip.to_search_text()
    assert "Paris" in text
    assert "France" in text
    assert "1299" in text
    assert "Eiffel Tower" in text

