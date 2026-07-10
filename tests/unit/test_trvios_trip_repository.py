"""Unit tests for Trvios trip mapping."""

from clean_app.infrastructure.persistence.trvios_trip_repository import _map_trvios_trip


def test_map_trvios_trip_parses_duration_and_price() -> None:
    trip = _map_trvios_trip(
        {
            "_id": "69878f13f5915890628bac43",
            "title": "Manali Snow Adventure",
            "destination": "Manali",
            "duration": "5 Days / 4 Nights",
            "price": 18999,
            "discountPrice": 15999,
            "highlights": ["Solang Valley snow activities", "Rohtang Pass excursion"],
            "tags": ["Mountains", "Adventurous"],
            "seasons": ["Winter Wonderland"],
            "states": ["Himachal Pradesh"],
            "itinerary": [
                {
                    "day": 1,
                    "title": "Arrival in Manali",
                    "description": "Hotel check-in.",
                    "activities": ["Check-in"],
                    "location": {"formattedAddress": "Manali, HP"},
                }
            ],
        }
    )

    assert trip.id == "69878f13f5915890628bac43"
    assert trip.duration_days == 5
    assert trip.price == 15999
    assert trip.currency == "INR"
    assert trip.country == "Himachal Pradesh"
    assert "Solang Valley" in trip.description
    assert len(trip.itinerary) == 1
    assert trip.itinerary[0].day == 1
    assert trip.itinerary[0].title == "Arrival in Manali"
    assert trip.itinerary[0].formatted_address == "Manali, HP"

