"""Unit tests for the places API and services."""

from unittest.mock import AsyncMock, MagicMock
import pytest
from clean_app.domain.entities.place_details import PlaceDetails
from clean_app.infrastructure.persistence.mongo_place_details_repository import MongoPlaceDetailsRepository
from clean_app.application.use_cases.get_place_details import GetPlaceDetailsUseCase
from clean_app.infrastructure.config.settings import Settings


def test_place_details_entity() -> None:
    place = PlaceDetails(
        name="India",
        place_type="country",
        description="A beautiful country in South Asia.",
        capital="New Delhi",
        currency="INR",
        languages=["Hindi", "English"],
        population="1.4 Billion",
        climate="Tropical",
        tourist_places=["Taj Mahal", "Goa Beaches"],
        popular_foods=["Butter Chicken", "Biryani"],
        festivals=["Diwali", "Holi"],
        history="Rich ancient civilization history.",
        parent_region=None,
        additional_info={}
    )
    assert place.name == "India"
    assert place.place_type == "country"
    assert "Taj Mahal" in place.tourist_places
    assert "Butter Chicken" in place.popular_foods
    assert place.capital == "New Delhi"


@pytest.mark.asyncio
async def test_places_repository_fallback(tmp_path) -> None:
    # Set settings to point fallback file to a temp path so we don't write to workspace root during testing
    settings = Settings(mongodb_uri="mongodb://invalid-host:9999")
    repo = MongoPlaceDetailsRepository(settings)
    
    # Override fallback file to temp directory
    repo._fallback_file = tmp_path / ".places_fallback_test.json"
    repo._mem_db = {}

    place = PlaceDetails(
        name="Goa",
        place_type="state",
        description="India's smallest state by area, known for beaches.",
        capital="Panaji",
        currency="INR",
        languages=["Konkani"],
        population="1.5 Million",
        climate="Tropical",
        tourist_places=["Calangute", "Baga"],
        popular_foods=["Vindaloo", "Fish Curry"],
        festivals=["Shigmo"],
        history="Former Portuguese colony.",
        parent_region="India",
        additional_info={}
    )

    await repo.save(place)
    
    # Retrieve
    retrieved = await repo.get_by_name("goa")
    assert retrieved is not None
    assert retrieved.name == "Goa"
    assert retrieved.parent_region == "India"
    assert retrieved.capital == "Panaji"

    # Case insensitivity test
    retrieved_case = await repo.get_by_name("GOA ")
    assert retrieved_case is not None
    assert retrieved_case.name == "Goa"

    # Non-existent
    assert await repo.get_by_name("non-existent") is None


@pytest.mark.asyncio
async def test_get_place_details_use_case() -> None:
    mock_repo = AsyncMock()
    mock_repo.get_by_name.return_value = None  # Cache miss

    mock_ollama = AsyncMock()
    mock_ollama.generate_place_details.return_value = {
        "name": "Karnataka",
        "place_type": "state",
        "description": "A state in southwest India.",
        "capital": "Bengaluru",
        "currency": "INR",
        "languages": ["Kannada"],
        "population": "61 Million",
        "climate": "Tropical wet-and-dry",
        "tourist_places": ["Bengaluru", "Hampi", "Mysuru"],
        "popular_foods": ["Bisi Bele Bath", "Dosa"],
        "festivals": ["Dasara", "Ugadi"],
        "history": "Ruled by famous empires like Chalukya & Hoysala.",
        "parent_region": "India",
        "additional_info": {}
    }

    use_case = GetPlaceDetailsUseCase(mock_repo, mock_ollama)
    result = await use_case.execute("Karnataka")

    assert result.name == "Karnataka"
    assert result.place_type == "state"
    assert "Bengaluru" in result.tourist_places
    mock_repo.get_by_name.assert_called_once_with("Karnataka")
    mock_ollama.generate_place_details.assert_called_once_with("Karnataka")
    mock_repo.save.assert_called_once()


@pytest.mark.asyncio
async def test_ollama_service_fallback() -> None:
    from clean_app.infrastructure.ai.ollama_service import OllamaService
    # Initialize settings with no OpenAI key and invalid Ollama host to force fallback
    settings = Settings(
        mongodb_uri="mongodb://invalid-host:9999",
        openai_api_key=None,
        ollama_model="llama3.2"
    )
    service = OllamaService(settings)
    
    # Override base URL to ensure immediate connection failure
    service._base_url = "http://invalid-ollama-host:11434"
    
    # Run details generation - should fall back to static generator
    details = await service.generate_place_details("India")
    assert details["name"] == "India"
    assert details["place_type"] == "country"
    assert "Taj Mahal" in details["tourist_places"]
    
    # Test for unknown place
    unknown_details = await service.generate_place_details("Atlantis")
    assert unknown_details["name"] == "Atlantis"
    assert unknown_details["place_type"] in ["country", "state", "city"]
    assert len(unknown_details["tourist_places"]) > 0

