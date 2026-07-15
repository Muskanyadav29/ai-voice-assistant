"""Use case for retrieving or generating place details."""

from clean_app.domain.entities.place_details import PlaceDetails
from clean_app.domain.repositories.place_details_repository import PlaceDetailsRepository
from clean_app.infrastructure.ai.ollama_service import OllamaService


class GetPlaceDetailsUseCase:
    """Manages the generation and database caching of country, state, and city details."""

    def __init__(
        self,
        place_details_repository: PlaceDetailsRepository,
        ollama_service: OllamaService
    ) -> None:
        self._repository = place_details_repository
        self._ollama_service = ollama_service

    async def execute(self, name: str) -> PlaceDetails:
        """Fetch details for a place from the repository. If not present, generate and save it."""
        cleaned_name = name.strip()
        if not cleaned_name:
            raise ValueError("Location name cannot be empty")
        
        # Check cache/db first
        cached_details = await self._repository.get_by_name(cleaned_name)
        if cached_details:
            # Check if this is a complete, new-schema document
            is_complete = (
                cached_details.tourist_places and
                cached_details.popular_foods and
                cached_details.festivals and
                cached_details.history
            )
            if is_complete:
                return cached_details
            print(f"Cached entry for '{cleaned_name}' is incomplete or uses old schema. Regenerating...")

        # Generate using Ollama
        details_dict = await self._ollama_service.generate_place_details(cleaned_name)
        
        # Parse fields from the generated response (handle potential case mismatch in keys)
        place_details = PlaceDetails(
            name=details_dict.get("name", cleaned_name),
            place_type=details_dict.get("place_type", "country"),
            description=details_dict.get("description", ""),
            capital=details_dict.get("capital"),
            currency=details_dict.get("currency"),
            languages=details_dict.get("languages", []),
            population=details_dict.get("population"),
            climate=details_dict.get("climate"),
            tourist_places=details_dict.get("tourist_places", []),
            popular_foods=details_dict.get("popular_foods", []),
            festivals=details_dict.get("festivals", []),
            history=details_dict.get("history"),
            parent_region=details_dict.get("parent_region"),
            additional_info=details_dict.get("additional_info", {})
        )

        # Save to database
        await self._repository.save(place_details)
        
        return place_details
