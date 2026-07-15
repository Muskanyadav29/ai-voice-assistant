"""Place details API routes."""

from fastapi import APIRouter, Request, HTTPException
from clean_app.presentation.api.schemas import PlaceRequestSchema, PlaceDetailsResponseSchema

router = APIRouter(prefix="", tags=["location"])


def _map_response(result) -> PlaceDetailsResponseSchema:
    """Helper to convert domain entity to Pydantic schema."""
    formatted_info = {}
    if result.additional_info:
        for k, v in result.additional_info.items():
            formatted_info[k] = str(v) if v is not None else None
            
    return PlaceDetailsResponseSchema(
        name=result.name,
        place_type=result.place_type,
        description=result.description,
        capital=result.capital,
        currency=result.currency,
        languages=result.languages,
        population=result.population,
        climate=result.climate,
        tourist_places=result.tourist_places,
        popular_foods=result.popular_foods,
        festivals=result.festivals,
        history=result.history,
        parent_region=result.parent_region,
        additional_info=formatted_info
    )


@router.post("/location/search", response_model=PlaceDetailsResponseSchema)
async def search_location(
    payload: PlaceRequestSchema,
    request: Request
) -> PlaceDetailsResponseSchema:
    """Fetch details for a location (country, state, city) by name.

    Classifies the location type and generates details via Ollama,
    saving the result persistently to MongoDB.
    """
    use_case = request.app.state.container.get_place_details
    try:
        result = await use_case.execute(payload.name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    return _map_response(result)


@router.get("/location", response_model=list[PlaceDetailsResponseSchema])
async def list_locations(request: Request) -> list[PlaceDetailsResponseSchema]:
    """List all stored locations in search history."""
    repo = request.app.state.container.get_place_details._repository
    places = await repo.get_all()
    return [_map_response(x) for x in places]



