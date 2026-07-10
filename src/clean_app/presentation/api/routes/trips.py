"""Trip API routes."""

from dataclasses import asdict

from fastapi import APIRouter, Request

from clean_app.presentation.api.schemas import IndexTripsSchema, TripSchema

router = APIRouter(prefix="/trips", tags=["trips"])


@router.get("", response_model=list[TripSchema])
def list_trips(request: Request) -> list[TripSchema]:
    """Return all trips from the configured catalog."""
    trips = request.app.state.container.list_trips.execute()
    return [TripSchema(**asdict(trip)) for trip in trips]


@router.post("/index", response_model=IndexTripsSchema)
def index_trips(request: Request) -> IndexTripsSchema:
    """Embed trips into the vector store for semantic search."""
    result = request.app.state.container.index_trips.execute()
    return IndexTripsSchema(
        indexed_count=result.indexed_count,
        total_in_store=result.total_in_store,
    )
