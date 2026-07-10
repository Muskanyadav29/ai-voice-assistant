import pytest
from clean_app.domain.entities.trip import Trip
from clean_app.domain.repositories.vector_store import TripSearchResult
from clean_app.infrastructure.ai.intent_ner_service import is_well_being_query, IntentNERService
from clean_app.infrastructure.ai.chat_service import TemplateChatService
from clean_app.infrastructure.config.settings import Settings


def test_is_well_being_query() -> None:
    assert is_well_being_query("I feel sad") is True
    assert is_well_being_query("I am not well today") is True
    assert is_well_being_query("I feel sick") is True
    assert is_well_being_query("I had a bad day") is True
    assert is_well_being_query("Can we search for trips to Udaipur?") is False
    assert is_well_being_query("Hello chatbot") is False


@pytest.mark.asyncio
async def test_fallback_nlu_well_being() -> None:
    # Set settings with dummy values
    settings = Settings(
        app_env="test",
        app_debug=True,
        chroma_persist_dir="./data/chroma",
        auto_index_trips=False,
        trip_source="static",
        openai_api_key="", # Blank key to trigger fallback exception in NLU
        openai_model="gpt-4o-mini"
    )
    
    nlu_service = IntentNERService(settings)
    
    # Test fallback classification for sad query
    result_sad = await nlu_service.analyze_query("I feel sad and down")
    assert result_sad.intent == "WELL_BEING"
    
    # Test fallback classification for normal greeting/other
    result_other = await nlu_service.analyze_query("hello chatbot")
    assert result_other.intent == "SMALL_TALK"


@pytest.mark.asyncio
async def test_template_chat_service_well_being() -> None:
    chat_service = TemplateChatService()
    
    trip_relaxing = Trip(
        id="trip-bali-wellness",
        title="Bali Wellness Retreat",
        destination="Ubud",
        country="Indonesia",
        duration_days=7,
        price=15000.0,
        currency="INR",
        description="Spa and yoga.",
        tags=("wellness", "relaxation"),
        start_date="2026-11-12",
        highlights=(),
        itinerary=(),
    )
    
    search_results = [TripSearchResult(trip=trip_relaxing, score=0.9)]
    
    # Test voice mode response contents
    voice_chunks = []
    async for chunk in chat_service.stream_answer(
        query="I am not well",
        results=search_results,
        voice_mode=True
    ):
        voice_chunks.append(chunk)
    
    voice_resp = "".join(voice_chunks)
    assert "sorry to hear" in voice_resp.lower() or "take care of yourself" in voice_resp.lower()
    assert "bali wellness retreat" in voice_resp.lower()
    
    # Test web mode response contents
    web_chunks = []
    async for chunk in chat_service.stream_answer(
        query="I feel sad",
        results=search_results,
        voice_mode=False
    ):
        web_chunks.append(chunk)
        
    web_resp = "".join(web_chunks)
    assert "really sorry" in web_resp.lower()
    assert "bali wellness retreat" in web_resp.lower()
    assert "change of scenery" in web_resp.lower()
