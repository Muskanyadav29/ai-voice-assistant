import pytest
from unittest.mock import AsyncMock, MagicMock

from clean_app.infrastructure.ai.intent_ner_service import IntentNERService, ParsedEntities, IntentNERResult
from clean_app.application.use_cases.chat_with_trips import ChatWithTripsUseCase
from clean_app.application.dto.trip_dto import ChatRequest
from clean_app.domain.entities.trip import Trip
from clean_app.infrastructure.config.settings import Settings


@pytest.mark.asyncio
async def test_list_trips_intent_fallback() -> None:
    settings = Settings(openai_api_key=None)
    nlu_service = IntentNERService(settings)
    
    # Test local keyword fallback
    res1 = await nlu_service.analyze_query("list all the trips")
    assert res1.intent == "LIST_TRIPS"
    
    res2 = await nlu_service.analyze_query("show all trips")
    assert res2.intent == "LIST_TRIPS"


@pytest.mark.asyncio
async def test_budget_parsing_fallback() -> None:
    settings = Settings(openai_api_key=None)
    nlu_service = IntentNERService(settings)
    
    # Test min and max budget parsing in rule-based fallback
    res1 = await nlu_service.analyze_query("recommend me a trip under budget 5000 rupees")
    assert res1.entities.max_budget == 5000.0
    assert res1.entities.min_budget is None
    
    res2 = await nlu_service.analyze_query("recommend me a trip above 7000 rupees")
    assert res2.entities.min_budget == 7000.0
    assert res2.entities.max_budget is None

    res3 = await nlu_service.analyze_query("show me the cheapest trip")
    assert res3.entities.sort_by_cheapest is True


@pytest.mark.asyncio
async def test_list_trips_use_case_execution() -> None:
    # Setup mock trips
    mock_trip = Trip(
        id="t1",
        title="Test Trip",
        destination="Test Dest",
        country="Test Country",
        duration_days=3,
        price=100.0,
        currency="INR",
        description="A great test trip",
        tags=(),
        start_date="Summer",
        highlights=(),
        itinerary=(),
    )
    
    # Mock repository
    mock_repo = MagicMock()
    mock_repo.get_all.return_value = [mock_trip]
    
    # Mock dependencies
    mock_vector = MagicMock()
    mock_booking = MagicMock()
    mock_chat = AsyncMock()
    
    # Mock stream_custom_prompt to yield chunks
    async def mock_stream(*args, **kwargs):
        yield "Here is the trip list"
        yield " - Test Trip"
    
    mock_chat.stream_custom_prompt = mock_stream
    
    mock_nlu = AsyncMock()
    mock_nlu.analyze_query.return_value = IntentNERResult(
        intent="LIST_TRIPS",
        cleaned_query="list all the trips",
        language="en",
        entities=ParsedEntities()
    )
    
    mock_memory = MagicMock()
    mock_memory.get_history_for_llm.return_value = []
    
    mock_recommend = MagicMock()
    mock_safety = AsyncMock()
    mock_safety.is_safe.return_value = True
    
    mock_book_use_case = MagicMock()
    
    use_case = ChatWithTripsUseCase(
        vector_store=mock_vector,
        trip_repo=mock_repo,
        booking_repo=mock_booking,
        chat_service=mock_chat,
        intent_ner_service=mock_nlu,
        memory_manager=mock_memory,
        recommendation_engine=mock_recommend,
        safety_service=mock_safety,
        book_trip_use_case=mock_book_use_case,
    )
    
    request = ChatRequest(query="list all the trips", top_k=2, session_id="s1")
    
    events = []
    async for event in use_case.stream_execute(request):
        events.append(event)
        
    # Check that sources contains the mock trip and tokens are yielded
    event_types = [e["type"] for e in events]
    assert "sources" in event_types
    assert "token" in event_types
    assert "done" in event_types
    
    sources_event = next(e for e in events if e["type"] == "sources")
    assert len(sources_event["sources"]) == 1
    assert sources_event["sources"][0]["id"] == "t1"
