"""FastAPI routes for bookings."""

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/bookings", tags=["bookings"])


class BookingCreateSchema(BaseModel):
    trip_id: str
    customer_name: str = "Valued Customer"


class BookingResponseSchema(BaseModel):
    id: str
    trip_id: str
    trip_title: str
    customer_name: str
    booking_date: str
    price: float
    status: str


@router.get("", response_model=list[BookingResponseSchema])
def list_bookings(request: Request) -> list[BookingResponseSchema]:
    """Retrieve all trip bookings."""
    container = request.app.state.container
    bookings = container.booking_repository.get_all()
    # Sort bookings by booking date / id desc
    return [
        BookingResponseSchema(
            id=b.id,
            trip_id=b.trip_id,
            trip_title=b.trip_title,
            customer_name=b.customer_name,
            booking_date=b.booking_date,
            price=b.price,
            status=b.status,
        )
        for b in sorted(bookings, key=lambda x: x.id, reverse=True)
    ]


@router.post("", response_model=BookingResponseSchema)
def create_booking(request: Request, body: BookingCreateSchema) -> BookingResponseSchema:
    """Manually book a trip."""
    container = request.app.state.container
    try:
        booking = container.book_trip.execute(body.trip_id, body.customer_name)
        return BookingResponseSchema(
            id=booking.id,
            trip_id=booking.trip_id,
            trip_title=booking.trip_title,
            customer_name=booking.customer_name,
            booking_date=booking.booking_date,
            price=booking.price,
            status=booking.status,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Booking failed: {e}")
