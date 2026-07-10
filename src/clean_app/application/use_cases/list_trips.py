from clean_app.application.dto.trip_dto import ItineraryItemResponse, TripResponse
from clean_app.domain.entities.trip import Trip
from clean_app.domain.repositories.trip_repository import TripRepository


def _to_response(trip: Trip) -> TripResponse:
    return TripResponse(
        id=trip.id,
        title=trip.title,
        destination=trip.destination,
        country=trip.country,
        duration_days=trip.duration_days,
        price=trip.price,
        currency=trip.currency,
        description=trip.description,
        tags=list(trip.tags),
        start_date=trip.start_date,
        highlights=list(trip.highlights),
        itinerary=[
            ItineraryItemResponse(
                day=item.day,
                title=item.title,
                description=item.description,
                activities=list(item.activities),
                formatted_address=item.formatted_address,
            )
            for item in trip.itinerary
        ],
    )



class ListTripsUseCase:
    """Return all available trips."""

    def __init__(self, trip_repository: TripRepository) -> None:
        self._trip_repository = trip_repository

    def execute(self) -> list[TripResponse]:
        return [_to_response(trip) for trip in self._trip_repository.get_all()]
