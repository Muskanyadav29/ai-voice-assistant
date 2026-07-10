import pytest
from pathlib import Path
from clean_app.infrastructure.ai.intent_ner_service import preprocess_text, is_well_being_query
from clean_app.infrastructure.ai.static_itinerary_engine import StaticItineraryEngine
from clean_app.infrastructure.ai.weather_service import map_weather_code, WeatherService


def test_text_preprocessing() -> None:
    # 1. Test punctuation removal and normalization
    raw_query = "Plan a trip to Manali, with 3 days!! and budget: Medium??"
    cleaned = preprocess_text(raw_query)
    assert cleaned == "plan a trip to manali with 3 days and budget medium"

    # 2. Test whitespace normalization
    raw_whitespace = "  Udaipur  trip  for   5   days   "
    cleaned_whitespace = preprocess_text(raw_whitespace)
    assert cleaned_whitespace == "udaipur trip for 5 days"


def test_weather_code_mapping() -> None:
    assert map_weather_code(0) == "Clear Sky"
    assert map_weather_code(3) == "Overcast"
    assert map_weather_code(95) == "Thunderstorm"
    assert map_weather_code(999) == "Unknown/Moderate"


@pytest.mark.asyncio
async def test_static_itinerary_engine_lookup() -> None:
    # Construct paths relative to tests
    engine = StaticItineraryEngine()
    
    # 1. Test template retrieval for Manali (sliced to 2 days)
    manali_2d = await engine.get_template("Manali", 2)
    assert manali_2d["destination"] == "Manali"
    assert len(manali_2d["days"]) == 2
    assert manali_2d["days"][0]["day"] == 1
    assert manali_2d["days"][1]["day"] == 2
    
    # 2. Test template retrieval for Manali (padded to 4 days)
    manali_4d = await engine.get_template("Manali", 4)
    assert len(manali_4d["days"]) == 4
    assert manali_4d["days"][3]["day"] == 4
    assert "Discover more" in manali_4d["days"][3]["title"]

    # 3. Test fallback template for unknown destination
    unknown = await engine.get_template("Atlantis", 3)
    assert unknown["destination"] == "Atlantis"
    assert len(unknown["days"]) == 3
    assert unknown["days"][0]["title"] == "Explore Atlantis - Day 1"


def test_prompt_structures() -> None:
    from clean_app.infrastructure.ai.intent_ner_service import ParsedEntities
    entities = ParsedEntities(
        destination="Manali", 
        max_budget=20000.0, 
        duration_days=3, 
        budget_level="High", 
        couple=True
    )
    assert entities.destination == "Manali"
    assert entities.budget_level == "High"
    assert entities.couple is True

