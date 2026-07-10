"""Unit tests for the travel recommendation engine."""

from clean_app.domain.entities.trip import Trip
from clean_app.infrastructure.ai.intent_ner_service import ParsedEntities
from clean_app.infrastructure.ai.recommendation_engine import RecommendationEngine


def test_recommendation_engine_filtering() -> None:
    engine = RecommendationEngine()
    
    trip_manali = Trip(
        id="trip-manali",
        title="Manali Adventure",
        destination="Manali",
        country="India",
        duration_days=5,
        price=18000.0,
        currency="INR",
        description="Snow peaks and activities.",
        tags=("adventure", "snow", "hiking"),
        start_date="Winter",
        highlights=(),
        itinerary=(),
    )
    
    trip_udaipur = Trip(
        id="trip-udaipur",
        title="Udaipur Heritage Tour",
        destination="Udaipur",
        country="India",
        duration_days=3,
        price=15000.0,
        currency="INR",
        description="Heritage and lakes.",
        tags=("heritage", "culture"),
        start_date="Year-round",
        highlights=(),
        itinerary=(),
    )
    
    trip_expensive = Trip(
        id="trip-expensive",
        title="Luxury Resort Stay",
        destination="Goa",
        country="India",
        duration_days=4,
        price=50000.0,
        currency="INR",
        description="Beach luxury.",
        tags=("beach", "luxury"),
        start_date="Summer",
        highlights=(),
        itinerary=(),
    )

    all_trips = [trip_manali, trip_udaipur, trip_expensive]

    # Test 1: Match by destination and budget
    entities_1 = ParsedEntities(
        destination="Manali",
        max_budget=20000.0,
        duration_days=5,
    )
    recs_1 = engine.recommend_trips(all_trips, entities_1)
    assert len(recs_1) > 0
    assert recs_1[0].trip.id == "trip-manali"

    # Test 2: Match by budget limit strictly
    entities_2 = ParsedEntities(
        max_budget=16000.0,
    )
    recs_2 = engine.recommend_trips(all_trips, entities_2)
    # trip_manali (18000) is slightly above 16000 but within 15% range (+15% of 16000 is 18400)
    # trip_udaipur (15000) is within budget
    # trip_expensive (50000) is completely out
    ids_returned = [r.trip.id for r in recs_2]
    assert "trip-udaipur" in ids_returned
    assert "trip-manali" in ids_returned
    assert "trip-expensive" not in ids_returned
    # Udaipur should rank higher because it's strictly under budget
    assert recs_2[0].trip.id == "trip-udaipur"

    # Test 3: Match tags/activities
    entities_3 = ParsedEntities(
        activities=["culture", "heritage"],
    )
    recs_3 = engine.recommend_trips(all_trips, entities_3)
    assert len(recs_3) > 0
    assert recs_3[0].trip.id == "trip-udaipur"
