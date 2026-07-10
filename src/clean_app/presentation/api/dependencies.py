"""FastAPI dependency wiring."""

from dataclasses import dataclass

from clean_app.application.use_cases.chat_with_trips import ChatWithTripsUseCase
from clean_app.application.use_cases.index_trips import IndexTripsUseCase
from clean_app.application.use_cases.list_trips import ListTripsUseCase
from clean_app.application.use_cases.book_trip import BookTripUseCase
from clean_app.application.use_cases.index_knowledge import IndexKnowledgeUseCase
from clean_app.application.use_cases.modify_itinerary import ModifyItineraryUseCase

from clean_app.domain.repositories.trip_repository import TripRepository
from clean_app.domain.repositories.vector_store import VectorStore
from clean_app.domain.repositories.booking_repository import BookingRepository

from clean_app.infrastructure.ai.chat_service import ChatService, build_chat_service
from clean_app.infrastructure.config.settings import Settings
from clean_app.infrastructure.persistence.static_trip_repository import StaticTripRepository
from clean_app.infrastructure.persistence.trvios_trip_repository import TrviosTripRepository
from clean_app.infrastructure.persistence.static_knowledge_repository import StaticKnowledgeRepository
from clean_app.infrastructure.persistence.in_memory_booking_repository import InMemoryBookingRepository
from clean_app.infrastructure.persistence.mongo_safety_repository import MongoSafetyRepository
from clean_app.infrastructure.vector.chroma_vector_store import ChromaVectorStore

from clean_app.infrastructure.ai.tts_stt_service import VoiceService
from clean_app.infrastructure.ai.intent_ner_service import IntentNERService
from clean_app.infrastructure.ai.memory_manager import MemoryManager
from clean_app.infrastructure.ai.recommendation_engine import RecommendationEngine
from clean_app.infrastructure.ai.safety_service import SafetyService
from clean_app.infrastructure.ai.google_places_service import GooglePlacesService
from clean_app.infrastructure.ai.weather_service import WeatherService
from clean_app.infrastructure.ai.static_itinerary_engine import StaticItineraryEngine
from clean_app.infrastructure.ai.google_directions_service import GoogleDirectionsService
from clean_app.infrastructure.ai.currency_service import CurrencyService



@dataclass
class AppContainer:
    """Shared application services for API routes."""

    settings: Settings
    trip_repository: TripRepository
    vector_store: VectorStore
    chat_service: ChatService
    list_trips: ListTripsUseCase
    index_trips: IndexTripsUseCase
    index_knowledge: IndexKnowledgeUseCase
    chat_with_trips: ChatWithTripsUseCase
    
    # New services
    booking_repository: BookingRepository
    voice_service: VoiceService
    intent_ner_service: IntentNERService
    memory_manager: MemoryManager
    recommendation_engine: RecommendationEngine
    safety_service: SafetyService
    book_trip: BookTripUseCase
    mongo_safety_repository: MongoSafetyRepository = None
    google_places_service: GooglePlacesService = None
    weather_service: WeatherService = None
    static_itinerary_engine: StaticItineraryEngine = None
    google_directions_service: GoogleDirectionsService = None
    currency_service: CurrencyService = None
    modify_itinerary: ModifyItineraryUseCase = None



def build_trip_repository(settings: Settings) -> TripRepository:
    """Pick the configured trip data source."""
    if settings.trip_source == "static":
        if settings.app_env == "test":
            return StaticTripRepository()
        raise ValueError(
            "Static trip source is not allowed in this environment. "
            "Please use the Trvios API."
        )
    return TrviosTripRepository(settings.trvios_trips_api_url)


def build_container(settings: Settings | None = None) -> AppContainer:
    """Construct the dependency container."""
    resolved_settings = settings or Settings.from_env()
    resolved_settings.ensure_directories()

    trip_repository = build_trip_repository(resolved_settings)
    knowledge_repository = StaticKnowledgeRepository()
    vector_store = ChromaVectorStore(resolved_settings.chroma_persist_dir)
    chat_service = build_chat_service(resolved_settings)

    # Initialize new dependencies
    booking_repository = InMemoryBookingRepository()
    mongo_safety_repository = MongoSafetyRepository(resolved_settings)
    voice_service = VoiceService(resolved_settings)
    intent_ner_service = IntentNERService(resolved_settings)
    memory_manager = MemoryManager()
    recommendation_engine = RecommendationEngine()
    safety_service = SafetyService(resolved_settings)
    book_trip_use_case = BookTripUseCase(booking_repository, trip_repository)
    modify_itinerary_use_case = ModifyItineraryUseCase(chat_service)

    # Instantiate Google Places, Weather, and Static Itinerary Engine
    google_places_service = GooglePlacesService(resolved_settings)
    weather_service = WeatherService()
    static_itinerary_engine = StaticItineraryEngine()
    google_directions_service = GoogleDirectionsService(resolved_settings)
    currency_service = CurrencyService()

    return AppContainer(
        settings=resolved_settings,
        trip_repository=trip_repository,
        vector_store=vector_store,
        chat_service=chat_service,
        list_trips=ListTripsUseCase(trip_repository),
        index_trips=IndexTripsUseCase(trip_repository, vector_store),
        index_knowledge=IndexKnowledgeUseCase(knowledge_repository, vector_store),
        booking_repository=booking_repository,
        voice_service=voice_service,
        intent_ner_service=intent_ner_service,
        memory_manager=memory_manager,
        recommendation_engine=recommendation_engine,
        safety_service=safety_service,
        book_trip=book_trip_use_case,
        mongo_safety_repository=mongo_safety_repository,
        google_places_service=google_places_service,
        weather_service=weather_service,
        static_itinerary_engine=static_itinerary_engine,
        google_directions_service=google_directions_service,
        currency_service=currency_service,
        modify_itinerary=modify_itinerary_use_case,
        chat_with_trips=ChatWithTripsUseCase(
            vector_store=vector_store,
            trip_repo=trip_repository,
            booking_repo=booking_repository,
            chat_service=chat_service,
            intent_ner_service=intent_ner_service,
            memory_manager=memory_manager,
            recommendation_engine=recommendation_engine,
            safety_service=safety_service,
            book_trip_use_case=book_trip_use_case,
            google_places_service=google_places_service,
            weather_service=weather_service,
            static_itinerary_engine=static_itinerary_engine,
            google_directions_service=google_directions_service,
            currency_service=currency_service,
            modify_itinerary_use_case=modify_itinerary_use_case,
        ),
    )

