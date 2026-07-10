"""Orchestrates the advanced AI chatbot pipeline."""

import asyncio
import urllib.parse
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

from clean_app.application.dto.trip_dto import ChatRequest, TripSourceResponse
from clean_app.domain.repositories.vector_store import TripSearchResult, KnowledgeSearchResult, VectorStore
from clean_app.domain.repositories.trip_repository import TripRepository
from clean_app.domain.repositories.booking_repository import BookingRepository
from clean_app.application.use_cases.book_trip import BookTripUseCase
from clean_app.infrastructure.ai.intent_ner_service import IntentNERService
from clean_app.infrastructure.ai.memory_manager import MemoryManager
from clean_app.infrastructure.ai.recommendation_engine import RecommendationEngine
from clean_app.infrastructure.ai.safety_service import SafetyService


class ChatService(ABC):
    """Port for generating natural-language answers from retrieved trips and platform knowledge."""

    @abstractmethod
    def stream_answer(
        self,
        query: str,
        results: list[TripSearchResult],
        knowledge_results: list[KnowledgeSearchResult] = None,
        voice_mode: bool = False,
    ) -> AsyncIterator[str]:
        """Stream a user-facing answer from search results."""

    @abstractmethod
    async def stream_freeform(
        self,
        query: str,
        conversation_history: list[dict[str, str]] = None,
        voice_mode: bool = False,
    ) -> AsyncIterator[str]:
        """Stream conversational replies without trip search results."""

    @abstractmethod
    def stream_custom_prompt(
        self,
        system_prompt: str,
        user_prompt: str,
        voice_mode: bool = False,
    ) -> AsyncIterator[str]:
        """Stream a response for a custom system and user prompt."""


def get_photo_url(place_type: str, photo_ref: str | None, key: str) -> str:
    """Construct Google Places photo url or fall back to high-quality Unsplash image."""
    if photo_ref and key:
        return f"https://maps.googleapis.com/maps/api/place/photo?maxwidth=400&photo_reference={photo_ref}&key={key}"
    
    # Premium fallbacks
    if place_type == "hotels":
        return "https://images.unsplash.com/photo-1566073771259-6a8506099945?w=400&auto=format&fit=crop"
    elif place_type == "restaurants":
        return "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=400&auto=format&fit=crop"
    else:  # attractions
        return "https://images.unsplash.com/photo-1469854523086-cc02fe5d8800?w=400&auto=format&fit=crop"


class ChatWithTripsUseCase:
    """Answer user questions using semantic trip search and modular handlers."""

    def __init__(
        self,
        vector_store: VectorStore,
        trip_repo: TripRepository,
        booking_repo: BookingRepository,
        chat_service: ChatService,
        intent_ner_service: IntentNERService,
        memory_manager: MemoryManager,
        recommendation_engine: RecommendationEngine,
        safety_service: SafetyService,
        book_trip_use_case: BookTripUseCase,
        google_places_service: Any = None,
        weather_service: Any = None,
        static_itinerary_engine: Any = None,
        google_directions_service: Any = None,
        currency_service: Any = None,
        modify_itinerary_use_case: Any = None,
    ) -> None:
        self._vector_store = vector_store
        self._trip_repo = trip_repo
        self._booking_repo = booking_repo
        self._chat_service = chat_service
        self._intent_ner_service = intent_ner_service
        self._memory_manager = memory_manager
        self._recommendation_engine = recommendation_engine
        self._safety_service = safety_service
        self._book_trip_use_case = book_trip_use_case
        self._google_places_service = google_places_service
        self._weather_service = weather_service
        self._static_itinerary_engine = static_itinerary_engine
        self._google_directions_service = google_directions_service
        self._currency_service = currency_service
        self._modify_itinerary_use_case = modify_itinerary_use_case

    async def stream_execute(self, request: ChatRequest) -> AsyncIterator[dict[str, Any]]:
        """Orchestrate the conversational agent pipeline."""
        session_id = request.session_id

        # 1. Safety check (Input Preprocessing & Guardrails)
        if not await self._safety_service.is_safe(request.query):
            yield {
                "type": "token",
                "content": "I'm sorry, but your request could not be processed as it violates safety guidelines."
            }
            yield {"type": "done", "query": request.query, "sources": [], "safety_flagged": True}
            return

        # 2. Context & History Retrieval
        history = self._memory_manager.get_history_for_llm(session_id)

        # 3. Intent Detection & NER Analysis
        analysis = await self._intent_ner_service.analyze_query(request.query, history)

        # Check if this is a questionnaire form submission
        is_form_submission = request.query.strip().startswith("[ITINERARY_SUBMIT:")
        if is_form_submission:
            analysis.intent = "ITINERARY"

        # Emit intent and entities metadata
        yield {
            "type": "metadata",
            "intent": analysis.intent,
            "entities": {
                "destination": analysis.entities.destination,
                "max_budget": analysis.entities.max_budget,
                "duration_days": analysis.entities.duration_days,
                "activities": analysis.entities.activities,
                "trip_id": analysis.entities.trip_id,
                "budget_level": analysis.entities.budget_level,
                "couple": analysis.entities.couple,
            },
            "cleaned_query": analysis.cleaned_query,
            "language": analysis.language,
        }

        # Fetch weather if destination is present
        weather_info = None
        destination = analysis.entities.destination
        if destination and self._weather_service:
            try:
                coords = None
                if self._google_places_service:
                    coords = await self._google_places_service.get_coordinates(destination)
                if coords:
                    weather_info = await self._weather_service.get_weather(coords[0], coords[1])
                else:
                    weather_info = await self._weather_service.get_mock_weather(destination)
            except Exception as e:
                print(f"Failed to fetch live weather: {e}")

        # Fetch currency rates if currency conversion is mentioned
        currency_info = None
        if self._currency_service and any(kw in request.query.lower() for kw in ["usd", "eur", "gbp", "inr", "convert", "currency", "rupee", "dollar"]):
            try:
                rates = await self._currency_service.get_conversion_rates()
                currency_info = rates
            except Exception as e:
                print(f"Failed to fetch live currency conversion: {e}")

        # Enrich analysis.cleaned_query with weather and currency info if found
        if weather_info or currency_info:
            extra_context = []
            if weather_info:
                extra_context.append(f"Live weather in {destination}: {weather_info.get('temperature')}, {weather_info.get('condition')}")
            if currency_info:
                rates_str = ", ".join(f"1 INR = {rate} {cur}" for cur, rate in currency_info.items())
                extra_context.append(f"Live currency exchange rates: {rates_str}")
            
            # Suffix the query sent to LLM with system-injected context
            analysis.cleaned_query = f"{analysis.cleaned_query} (System Context - {' | '.join(extra_context)})"

        # If user asks for trip recommendations but already specifies a destination, route directly to ITINERARY generation!
        if analysis.intent in ["TRIP_RECOMMENDATION", "WEATHER_BASED_TRIP", "MOOD_BASED_TRIP"] and analysis.entities.destination:
            analysis.intent = "ITINERARY"

        answer_chunks = []
        sources = []

        if analysis.intent == "ITINERARY":
            # If voice mode, check if we need to collect preferences first
            if request.voice_mode:
                extracted = await self._extract_preferences(request.query, history)
                destination = extracted.get("destination") or analysis.entities.destination
                days_raw = extracted.get("duration_days") or analysis.entities.duration_days
                budget = extracted.get("budget") or analysis.entities.budget_level
                mood = extracted.get("mood") or analysis.entities.mood
                travel_type = extracted.get("travel_type") or ("Couple" if analysis.entities.couple else None)

                # Check if budget was explicitly answered
                has_answered_budget = False
                if budget and budget != "Medium":
                    has_answered_budget = True
                else:
                    has_answered_budget = any(kw in request.query.lower() for kw in ["medium", "mid", "budget", "luxury", "range"])
                    if not has_answered_budget and history:
                        for msg in history:
                            if any(kw in msg["content"].lower() for kw in ["budget preference", "mid-range", "luxury", "stay preference"]):
                                has_answered_budget = True
                                break

                missing_slot = None
                follow_up_prompt = ""

                if not destination:
                    missing_slot = "destination"
                    follow_up_prompt = "I'd love to help you plan an itinerary! Which destination are you planning to visit?"
                elif not days_raw:
                    missing_slot = "duration_days"
                    follow_up_prompt = f"How many days are you planning to stay in {destination}?"
                elif not has_answered_budget:
                    missing_slot = "budget"
                    follow_up_prompt = "What is your budget preference? Budget, mid-range, or luxury?"
                elif not mood and not travel_type:
                    missing_slot = "mood"
                    follow_up_prompt = "Who are you traveling with, and what kind of mood or vibe are you looking for? E.g., a nature couple trip or an adventure solo trip?"

                if missing_slot:
                    # Yield words for streaming response
                    for word in follow_up_prompt.split(" "):
                        yield {"type": "token", "content": word + " "}
                        answer_chunks.append(word + " ")
                        await asyncio.sleep(0.01)

                    # Save user query and assistant response to history
                    self._memory_manager.add_message(session_id, "user", request.query)
                    self._memory_manager.add_message(session_id, "assistant", follow_up_prompt)

                    yield {
                        "type": "done",
                        "query": request.query,
                        "sources": [],
                        "validation": {
                            "safety_ok": True,
                            "hallucination_flagged": False,
                        }
                    }
                    return

            # If not form submission and not voice mode, prompt user for preferences first (web chat client form)
            if not is_form_submission and not request.voice_mode:
                destination = analysis.entities.destination or "Manali"
                days = analysis.entities.duration_days or 3
                form_content = f"[ITINERARY_FORM: destination={destination} | days={days}]"
                
                for word in form_content.split(" "):
                    yield {"type": "token", "content": word + " "}
                    answer_chunks.append(word + " ")
                    await asyncio.sleep(0.01)
                
                # Save user query to history
                self._memory_manager.add_message(session_id, "user", request.query)
                self._memory_manager.add_message(session_id, "assistant", form_content)
                
                yield {
                    "type": "done",
                    "query": request.query,
                    "sources": [],
                    "validation": {
                        "safety_ok": True,
                        "hallucination_flagged": False,
                    }
                }
                return

            # Resolve parameters based on form submission, voice mode preferences, or defaults
            if is_form_submission:
                # Parse: [ITINERARY_SUBMIT: destination=Udaipur | days=3 | travel_type=Couple | style=Active | mood=Nature | budget=Luxury | transport=Cab | stay=Resort | food=Veg | activity=Adventure]
                content = request.query.strip()[18:-1]
                parts = content.split("|")
                data = {}
                for part in parts:
                    idx = part.find("=")
                    if idx != -1:
                        k = part[:idx].strip().lower()
                        v = part[idx+1:].strip()
                        data[k] = v
                
                destination = data.get("destination", "Manali")
                try:
                    days = int(data.get("days", "3"))
                except ValueError:
                    days = 3
                
                travel_type = data.get("travel_type", "Couple")
                style = data.get("style", "Balanced")
                mood = data.get("mood", "Nature")
                budget_level = data.get("budget", "Mid-range")
                transport = data.get("transport", "Cab")
                stay_pref = data.get("stay", "Hotel")
                food_pref = data.get("food", "Veg")
                activity_pref = data.get("activity", "Sightseeing")
            elif request.voice_mode:
                # Extract preferences using LLM
                extracted = await self._extract_preferences(request.query, history)
                destination = extracted.get("destination") or analysis.entities.destination or "Manali"
                
                # Try to parse days
                days_raw = extracted.get("duration_days")
                if not days_raw:
                    days_raw = analysis.entities.duration_days or 3
                try:
                    days = int(days_raw)
                except (ValueError, TypeError):
                    days = 3

                travel_type = extracted.get("travel_type") or "Couple"
                style = extracted.get("style") or "Balanced"
                mood = extracted.get("mood") or "Nature"
                budget_level = extracted.get("budget") or "Mid-range"
                transport = extracted.get("transport") or "Cab"
                stay_pref = extracted.get("stay") or "Hotel"
                food_pref = extracted.get("food") or "Veg"
                activity_pref = extracted.get("activity") or "Sightseeing"
            else:
                # Basic fallback flow
                destination = analysis.entities.destination or "Manali"
                days = analysis.entities.duration_days or 3
                budget_level = analysis.entities.budget_level or "Medium"
                couple = analysis.entities.couple
                travel_type = "Couple" if couple else "Solo"
                style = "Balanced"
                mood = "Nature"
                transport = "Cab"
                stay_pref = "Hotel"
                food_pref = "Local Cuisine"
                activity_pref = "Sightseeing"

            # Geocode / retrieve coordinates using Google Places API
            coords = None
            if self._google_places_service:
                coords = await self._google_places_service.get_coordinates(destination)

            # Build Places queries dynamically based on preference slots
            stay_query_str = f"best {stay_pref.lower()}s in {destination}"
            
            food_pref_str = food_pref.lower()
            if food_pref_str == "veg":
                restaurants_query_str = f"best vegetarian restaurants in {destination}"
            elif food_pref_str == "cafés" or food_pref_str == "cafes":
                restaurants_query_str = f"best cafes in {destination}"
            else:
                restaurants_query_str = f"best restaurants in {destination}"

            act_pref_str = activity_pref.lower()
            if act_pref_str == "adventure":
                attractions_query_str = f"best adventure sports spots in {destination}"
            elif act_pref_str == "shopping":
                attractions_query_str = f"best shopping markets and bazaars in {destination}"
            elif act_pref_str == "temples":
                attractions_query_str = f"historical temples in {destination}"
            elif act_pref_str == "waterfalls":
                attractions_query_str = f"beautiful waterfalls and nature spots in {destination}"
            elif act_pref_str == "cafés" or act_pref_str == "cafes":
                attractions_query_str = f"best tourist cafes in {destination}"
            else:
                attractions_query_str = f"top tourist sightseeing attractions in {destination}"

            # Parallel external calls
            tasks = []
            if self._google_places_service:
                tasks.append(self._google_places_service.get_places(destination, stay_query_str, limit=3))
                tasks.append(self._google_places_service.get_places(destination, attractions_query_str, limit=5))
                tasks.append(self._google_places_service.get_places(destination, restaurants_query_str, limit=3))
            else:
                tasks.extend([asyncio.sleep(0, []), asyncio.sleep(0, []), asyncio.sleep(0, [])])

            if self._weather_service:
                if coords:
                    tasks.append(self._weather_service.get_weather(coords[0], coords[1]))
                else:
                    tasks.append(self._weather_service.get_mock_weather(destination))
            else:
                tasks.append(asyncio.sleep(0, {}))

            if self._static_itinerary_engine:
                tasks.append(self._static_itinerary_engine.get_template(destination, days))
            else:
                tasks.append(asyncio.sleep(0, {}))

            # Execute in parallel
            hotels, attractions, restaurants, weather, template = await asyncio.gather(*tasks)

            # Calculate Directions using Google Directions API in parallel
            directions_by_day = {}
            if template and "days" in template:
                directions_tasks = []
                route_keys = []
                for day_idx, day_data in enumerate(template["days"]):
                    stops = day_data.get("stops", [])
                    if len(stops) > 1:
                        for s_idx in range(len(stops) - 1):
                            orig = stops[s_idx]
                            dest = stops[s_idx + 1]
                            route_keys.append((day_idx, s_idx, orig, dest))
                            if self._google_directions_service:
                                directions_tasks.append(self._google_directions_service.get_directions(orig, dest))
                            else:
                                directions_tasks.append(asyncio.sleep(0, {}))
                
                if directions_tasks:
                    directions_results = await asyncio.gather(*directions_tasks)
                    for key, result in zip(route_keys, directions_results):
                        day_idx, s_idx, orig, dest = key
                        if day_idx not in directions_by_day:
                            directions_by_day[day_idx] = {}
                        directions_by_day[day_idx][s_idx] = result

            # Build Place Cards Data
            api_key = self._google_places_service.api_key if self._google_places_service else ""
            
            def build_cards(places_list, place_type):
                cards = []
                if not places_list:
                    return cards
                for p in places_list:
                    name = p.get("name", "Unknown Place")
                    rating = p.get("rating", 4.0)
                    addr = p.get("address", "N/A")
                    ref = p.get("photo_reference")
                    p_url = get_photo_url(place_type, ref, api_key)
                    q_str = urllib.parse.quote_plus(f"{name} {destination}")
                    m_url = f"https://www.google.com/maps/search/?api=1&query={q_str}"
                    cards.append({
                        "name": name,
                        "rating": rating,
                        "photo_url": p_url,
                        "maps_url": m_url,
                        "address": addr
                    })
                return cards

            compressed_hotels = []
            if hotels:
                for h in build_cards(hotels, "hotels"):
                    h["price"] = "₹4,200/night" if stay_pref.lower() == "resort" else "₹2,800/night"
                    h["amenities"] = "Free Breakfast, Swimming Pool, Scenic View" if stay_pref.lower() == "resort" else "Free Breakfast, Parking, Wifi"
                    compressed_hotels.append(h)

            compressed_attractions = []
            if attractions:
                for idx, a in enumerate(build_cards(attractions, "attractions")):
                    a["visit_time"] = "09:00 AM – 10:30 AM" if idx == 0 else "11:00 AM – 01:00 PM"
                    a["stay"] = "1 hr 30 min"
                    a["travel"] = "15 mins from previous stop"
                    a["entry"] = "Free"
                    a["reviews"] = "15K Reviews"
                    compressed_attractions.append(a)

            compressed_restaurants = []
            if restaurants:
                for r in build_cards(restaurants, "restaurants"):
                    r["cuisine"] = "Vegetarian, Traditional" if food_pref.lower() == "veg" else "Multi-cuisine, Local"
                    r["avg_cost"] = "₹600/person" if food_pref.lower() == "veg" else "₹800/person"
                    r["must_try"] = "Special Veg Thali, Local Sweets" if food_pref.lower() == "veg" else "Chef Special Dishes, Desserts"
                    compressed_restaurants.append(r)

            # Prompts for OpenAI beautification
            system_prompt = (
                "You are an expert travel assistant for Trvios, a technology-driven travel marketplace in India. "
                "Your task is to beautify, format, and structure the provided static itinerary template into a detailed day-by-day and hour-by-hour timeline plan.\n\n"
                "CRITICAL REQUIREMENTS:\n"
                "1. Organize your response exactly into the following sections using these markdown headers:\n"
                "# 🗺️ Beautiful Travel Itinerary for [Destination] ([Days] Days)\n\n"
                "## 🌦️ Current Weather\n"
                "- State current temperature and conditions.\n\n"
                "## 📅 Daily Plans\n"
                "For each day, structure it exactly like:\n"
                "### Day X: [Day Title]\n"
                "Construct a chronological schedule (e.g. '08:00 AM → 09:00 AM → 10:30 AM...') with realistic travel and visit durations.\n"
                "Each timeline stop (place) and travel segment MUST use these exact formats (do NOT invent headers, lists, or custom markdown styles inside these blocks):\n"
                "- Place Card:\n"
                "[CARD: type=attraction | name=... | rating=... | reviews=... | photo_url=... | maps_url=... | address=... | visit_time=... | stay=... | travel=... | entry=...]\n"
                "- Restaurant Card:\n"
                "[CARD: type=restaurant | name=... | rating=... | photo_url=... | maps_url=... | address=... | cuisine=... | avg_cost=... | must_try=...]\n"
                "- Travel Segment (place in-between stop cards):\n"
                "[TRAVEL: leave_time=... | travel_time=... | distance=... | navigation_link=...]\n\n"
                "2. Recommended Stays Section:\n"
                "## 🏨 Recommended Stays\n"
                "For each hotel, output this exact CARD tag format (do NOT create regular text or bullet lists, ONLY output these CARD tags):\n"
                "[CARD: type=hotel | name=... | rating=... | photo_url=... | maps_url=... | address=... | price=... | amenities=...]\n\n"
                "3. Estimated Budget Section:\n"
                "## 💰 Estimated Budget\n"
                "- State the Budget Level preference. Provide a detailed cost breakdown for Stay, Food, Transport, and Activities in INR, and show the Estimated Total Cost Range.\n\n"
                "CRITICAL: Do NOT write literal placeholders like 'photo_url' or 'maps_url' inside CARD and TRAVEL tags! You MUST copy the exact string values from the context lists:\n"
                "- Stays context details: Suggested Hotels list.\n"
                "- Attractions context details: Suggested Attractions list.\n"
                "- Restaurants context details: Suggested Restaurants list.\n"
                "- Travel Directions context details: Directions by Day list.\n\n"
                "Keep the tone premium and engaging. Use clean markdown formatting and headers (e.g., #, ##, ###) to make the text beautiful and easy to read on the user's screen.\n\n"
                "CONTINUOUS CONVERSATION & REAL-TIME UPDATES:\n"
                "If the user asks to modify the itinerary based on the context of conversation history (e.g., 'change my hotel', 'add a cafe', 'skip this place', 'increase my budget', 'make it more relaxing', 'navigate to next destination'), "
                "you MUST rewrite/update the previous itinerary to apply the requested changes, while keeping the rest of the travel plan and formatting intact."
            )

            user_prompt = (
                f"Destination: {destination}\n"
                f"Days: {days}\n"
                f"Travel Type: {travel_type}\n"
                f"Itinerary Style: {style}\n"
                f"Mood: {mood}\n"
                f"Budget Level: {budget_level}\n"
                f"Transport Preference: {transport}\n"
                f"Stay Preference: {stay_pref}\n"
                f"Food Preference: {food_pref}\n"
                f"Activity Preference: {activity_pref}\n"
                f"Static Template: {template}\n"
                f"Top Suggested Stays: {compressed_hotels}\n"
                f"Top Suggested Attractions: {compressed_attractions}\n"
                f"Top Suggested Restaurants: {compressed_restaurants}\n"
                f"Current Weather: {weather}\n"
                f"Directions by Day: {directions_by_day}\n"
                f"User History Context: {history[-3:] if history else 'None'}\n"
                f"User Request: {analysis.cleaned_query}"
            )

            async for token in self._chat_service.stream_custom_prompt(system_prompt, user_prompt, request.voice_mode):
                yield {"type": "token", "content": token}
                answer_chunks.append(token)

        elif analysis.intent in ["TRIP_RECOMMENDATION", "WEATHER_BASED_TRIP", "MOOD_BASED_TRIP"]:
            # Context analysis slots
            mood = analysis.entities.mood
            weather = analysis.entities.weather
            occasion = analysis.entities.occasion
            budget = analysis.entities.budget_level
            duration = analysis.entities.duration_days

            all_trips = self._trip_repo.get_all()
            matched_trips = []

            for trip in all_trips:
                score = 0
                trip_text = (trip.title + " " + trip.destination + " " + trip.description + " " + " ".join(trip.tags)).lower()

                # Mood matching
                if mood:
                    if mood.lower() in ["feeling low", "stressed", "sad", "relaxation", "wellness"]:
                        if any(kw in trip_text for kw in ["relax", "retreat", "soothing", "peace", "calm", "hills", "spiritual"]):
                            score += 3
                    elif mood.lower() in ["romantic", "honeymoon"]:
                        if any(kw in trip_text for kw in ["couple", "romantic", "retreat", "honeymoon", "scenic"]):
                            score += 3
                    elif mood.lower() in ["excited", "adventure", "active"]:
                        if any(kw in trip_text for kw in ["adventure", "trek", "sport", "rafting", "bike", "active"]):
                            score += 3
                    elif mood.lower() in trip_text:
                        score += 3

                # Weather matching
                if weather:
                    if weather.lower() in ["snow", "cold"]:
                        if any(kw in trip_text for kw in ["snow", "winter", "himachal", "kashmir", "glacier"]):
                            score += 3
                    elif weather.lower() in ["sunny", "beach", "hot"]:
                        if any(kw in trip_text for kw in ["beach", "sunny", "goa", "kerala", "warm", "coast"]):
                            score += 3
                    elif weather.lower() in ["rainy", "monsoon"]:
                        if any(kw in trip_text for kw in ["monsoon", "rain", "waterfall", "lush"]):
                            score += 3
                    elif weather.lower() in trip_text:
                        score += 3

                # Occasion matching
                if occasion:
                    if occasion.lower() in ["weekend", "short"]:
                        if trip.duration_days <= 3:
                            score += 2
                    if occasion.lower() in ["family", "friends", "solo"]:
                        if occasion.lower() in trip_text:
                            score += 2
                    elif occasion.lower() in trip_text:
                        score += 2

                # Duration matching
                if duration:
                    if abs(trip.duration_days - duration) <= 1:
                        score += 1

                # Budget level matching
                if budget:
                    if budget.lower() in trip_text:
                        score += 1

                if score > 0:
                    matched_trips.append((trip, score))

            matched_trips.sort(key=lambda x: x[1], reverse=True)
            if not matched_trips:
                recommendations = all_trips[:3]
            else:
                recommendations = [t[0] for t in matched_trips[:3]]

            trip_info_list = []
            for t in recommendations:
                trip_info_list.append(f"- {t.title} in {t.destination}: {t.description} ({t.duration_days} days, price: {t.price})")
            
            recs_text = "\n".join(trip_info_list)

            system_prompt = (
                "You are TARA, a warm, professional travel concierge for Trvios (similar to Ixigo's voice assistant). Answering over a two-way voice call. "
                "CRITICAL: Always respond in the same language and style (English, Hindi, or Hinglish/Indian English) as the user's query. "
                "Recommend the best destinations based on the user's context (mood, weather, occasion). "
                "Briefly explain why each destination fits them. Keep the description extremely concise and spoken-friendly (under 50 words). "
                "Explicitly ask the user which of these destinations they prefer to plan a personalized day-wise itinerary for."
            )

            user_prompt = (
                f"User mood: {mood}, weather: {weather}, occasion: {occasion}, budget: {budget}, duration: {duration}. "
                f"Matching Trip Database Packages:\n{recs_text}"
            )

            async for token in self._chat_service.stream_custom_prompt(system_prompt, user_prompt, request.voice_mode):
                yield {"type": "token", "content": token}
                answer_chunks.append(token)

        elif analysis.intent == "HOTEL_SEARCH":
            destination = analysis.entities.destination or "Manali"
            
            # Parallel places search + weather
            coords = None
            if self._google_places_service:
                coords = await self._google_places_service.get_coordinates(destination)

            tasks = []
            if self._google_places_service:
                tasks.append(self._google_places_service.get_places(destination, "hotels", limit=3))
            else:
                tasks.append(asyncio.sleep(0, []))

            if self._weather_service:
                if coords:
                    tasks.append(self._weather_service.get_weather(coords[0], coords[1]))
                else:
                    tasks.append(self._weather_service.get_mock_weather(destination))
            else:
                tasks.append(asyncio.sleep(0, {}))

            hotels, weather = await asyncio.gather(*tasks)
            
            api_key = self._google_places_service.api_key if self._google_places_service else ""
            compressed_hotels = []
            if hotels:
                for h in hotels:
                    name = h.get("name", "Unknown Hotel")
                    rating = h.get("rating", 4.0)
                    addr = h.get("address", "N/A")
                    ref = h.get("photo_reference")
                    p_url = get_photo_url("hotels", ref, api_key)
                    q_str = urllib.parse.quote_plus(f"{name} {destination}")
                    m_url = f"https://www.google.com/maps/search/?api=1&query={q_str}"
                    compressed_hotels.append({
                        "name": name,
                        "rating": rating,
                        "photo_url": p_url,
                        "maps_url": m_url,
                        "address": addr,
                        "price": "₹3,500/night",
                        "amenities": "Free Breakfast, Parking, Mountain View"
                    })

            system_prompt = (
                "You are a travel assistant. Present these hotel recommendations as Place Cards.\n"
                "For each hotel, output this exact CARD tag format:\n"
                "[CARD: type=hotel | name=... | rating=... | photo_url=... | maps_url=... | address=... | price=... | amenities=...]\n"
                "CRITICAL: Extract and inject the exact values for 'name', 'rating', 'photo_url', 'maps_url', 'address', 'price', and 'amenities' from each hotel object in the provided context list.\n\n"
                "State the current weather conditions at the destination."
            )
            if request.voice_mode:
                system_prompt = "You are a helpful travel assistant on a two-way voice call. Present the top hotel recommendations in under 30 words in conversational text. Do not use markdown, lists, links, or CARD tags."

            user_prompt = f"Destination: {destination}. Hotels: {compressed_hotels}. Weather: {weather}."
            async for token in self._chat_service.stream_custom_prompt(system_prompt, user_prompt, request.voice_mode):
                yield {"type": "token", "content": token}
                answer_chunks.append(token)

        elif analysis.intent == "RESTAURANT_SEARCH":
            destination = analysis.entities.destination or "Manali"
            
            restaurants = []
            if self._google_places_service:
                restaurants = await self._google_places_service.get_places(destination, "restaurants", limit=5)

            api_key = self._google_places_service.api_key if self._google_places_service else ""
            compressed_restaurants = []
            if restaurants:
                for r in restaurants:
                    name = r.get("name", "Unknown Restaurant")
                    rating = r.get("rating", 4.0)
                    addr = r.get("address", "N/A")
                    ref = r.get("photo_reference")
                    p_url = get_photo_url("restaurants", ref, api_key)
                    q_str = urllib.parse.quote_plus(f"{name} {destination}")
                    m_url = f"https://www.google.com/maps/search/?api=1&query={q_str}"
                    compressed_restaurants.append({
                        "name": name,
                        "rating": rating,
                        "photo_url": p_url,
                        "maps_url": m_url,
                        "address": addr,
                        "cuisine": "North Indian, Cafe",
                        "avg_cost": "₹700/person",
                        "must_try": "Local Trout Fish, Wood-fired Pizza, Hot Coffee"
                    })

            system_prompt = (
                "You are a travel assistant. Present these restaurant recommendations as Place Cards.\n"
                "For each restaurant, output this exact CARD tag format:\n"
                "[CARD: type=restaurant | name=... | rating=... | photo_url=... | maps_url=... | address=... | cuisine=... | avg_cost=... | must_try=...]\n"
                "CRITICAL: Extract and inject the exact values for 'name', 'rating', 'photo_url', 'maps_url', 'address', 'cuisine', 'avg_cost', and 'must_try' from each restaurant object in the provided context list."
            )
            if request.voice_mode:
                system_prompt = "You are a helpful travel assistant on a two-way voice call. Present the top restaurant recommendations in under 30 words in conversational text. Do not use markdown, lists, links, or CARD tags."

            user_prompt = f"Destination: {destination}. Restaurants: {compressed_restaurants}."
            async for token in self._chat_service.stream_custom_prompt(system_prompt, user_prompt, request.voice_mode):
                yield {"type": "token", "content": token}
                answer_chunks.append(token)

        elif analysis.intent == "WEATHER":
            destination = analysis.entities.destination or "Manali"
            
            coords = None
            if self._google_places_service:
                coords = await self._google_places_service.get_coordinates(destination)

            weather = {}
            if self._weather_service:
                if coords:
                    weather = await self._weather_service.get_weather(coords[0], coords[1])
                else:
                    weather = await self._weather_service.get_mock_weather(destination)

            system_prompt = "You are a travel assistant. Describe this weather forecast in a friendly way."
            if request.voice_mode:
                system_prompt += " CRITICAL: Keep it under 20 words, simple, and speakable."

            user_prompt = f"Destination: {destination}. Weather: {weather}."
            async for token in self._chat_service.stream_custom_prompt(system_prompt, user_prompt, request.voice_mode):
                yield {"type": "token", "content": token}
                answer_chunks.append(token)

        elif analysis.intent == "ITINERARY_MODIFY":
            last_itinerary = None
            for msg in reversed(history):
                if msg["role"] == "assistant" and any(marker in msg["content"] for marker in ["Itinerary", "Day ", "CARD:", "Timeline"]):
                    last_itinerary = msg["content"]
                    break
            
            if not last_itinerary:
                last_itinerary = "No active itinerary was found in your session. Please plan an itinerary first."

            modified_itinerary = "No changes applied."
            if self._modify_itinerary_use_case:
                modified_itinerary = await self._modify_itinerary_use_case.execute(last_itinerary, request.query)

            # Yield the modified itinerary words
            for word in modified_itinerary.split(" "):
                yield {"type": "token", "content": word + " "}
                answer_chunks.append(word + " ")
                if not request.voice_mode:
                    await asyncio.sleep(0.01)

        elif analysis.intent == "BOOKING":
            # Booking Handler: attempt to resolve trip to book
            matched_trip = None
            trip_ref = analysis.entities.trip_id or analysis.entities.destination

            if trip_ref:
                all_trips = self._trip_repo.get_all()
                # Try index matching first (e.g. "1", "first")
                if trip_ref.isdigit():
                    idx = int(trip_ref) - 1
                    if 0 <= idx < len(all_trips):
                        matched_trip = all_trips[idx]
                elif trip_ref.lower() in ["first", "1st"]:
                    if len(all_trips) > 0:
                        matched_trip = all_trips[0]
                elif trip_ref.lower() in ["second", "2nd"]:
                    if len(all_trips) > 1:
                        matched_trip = all_trips[1]
                elif trip_ref.lower() in ["third", "3rd"]:
                    if len(all_trips) > 2:
                        matched_trip = all_trips[2]
                
                # If not matched yet, try searching by id or title substring
                if not matched_trip:
                    for t in all_trips:
                        if t.id == trip_ref or trip_ref.lower() in t.title.lower() or trip_ref.lower() in t.destination.lower():
                            matched_trip = t
                            break

            if matched_trip:
                try:
                    booking = self._book_trip_use_case.execute(matched_trip.id, "Valued Customer")
                    booking_msg = (
                        f"🎉 **Booking Confirmed!**\n\n"
                        f"I have successfully registered your trip:\n"
                        f"- **Package:** {matched_trip.title}\n"
                        f"- **Destination:** {matched_trip.destination}, {matched_trip.country}\n"
                        f"- **Booking Code:** {booking.id}\n"
                        f"- **Price:** INR {booking.price:,.2f}\n"
                        f"- **Date:** {booking.booking_date}\n\n"
                        f"Your booking is confirmed! You can view it in the Bookings section."
                    )
                except Exception as e:
                    booking_msg = f"Sorry, I encountered an issue booking that trip: {e}"
            else:
                booking_msg = "Which trip would you like to book? Please specify the exact name of the tour or package."

            for word in booking_msg.split(" "):
                yield {"type": "token", "content": word + " "}
                answer_chunks.append(word + " ")
                await asyncio.sleep(0.02)

        elif analysis.intent == "PRICE_QUERY":
            # Search database for packages matching destination/budget
            all_trips = self._trip_repo.get_all()
            recommended = self._recommendation_engine.recommend_trips(all_trips, analysis.entities, top_n=request.top_k)
            knowledge_results = self._vector_store.search_knowledge(analysis.cleaned_query, top_k=2)

            if recommended:
                sources = [
                    TripSourceResponse(
                        id=res.trip.id,
                        title=res.trip.title,
                        destination=f"{res.trip.destination}, {res.trip.country}",
                        score=round(res.score, 4),
                    )
                    for res in recommended
                ]
                yield {
                    "type": "sources",
                    "sources": [
                        {"id": s.id, "title": s.title, "destination": s.destination, "score": s.score}
                        for s in sources
                    ],
                }
                async for token in self._chat_service.stream_answer(analysis.cleaned_query, recommended, knowledge_results, request.voice_mode):
                    yield {"type": "token", "content": token}
                    answer_chunks.append(token)
            else:
                results = self._vector_store.search(analysis.cleaned_query, top_k=request.top_k)
                sources = [
                    TripSourceResponse(
                        id=res.trip.id,
                        title=res.trip.title,
                        destination=f"{res.trip.destination}, {res.trip.country}",
                        score=round(res.score, 4),
                    )
                    for res in results
                ]
                yield {
                    "type": "sources",
                    "sources": [
                        {"id": s.id, "title": s.title, "destination": s.destination, "score": s.score}
                        for s in sources
                    ],
                }
                async for token in self._chat_service.stream_answer(analysis.cleaned_query, results, knowledge_results, request.voice_mode):
                    yield {"type": "token", "content": token}
                    answer_chunks.append(token)

        elif analysis.intent == "SPLIT_BILL":
            # Platform details about bill splitting/calculator
            knowledge_results = self._vector_store.search_knowledge(analysis.cleaned_query, top_k=2)
            async for token in self._chat_service.stream_answer(analysis.cleaned_query, [], knowledge_results, request.voice_mode):
                yield {"type": "token", "content": token}
                answer_chunks.append(token)

        else:  # GENERAL_QNA (or fallback small talk)
            # Check if this is a wellness/feelings query
            from clean_app.infrastructure.ai.intent_ner_service import is_well_being_query
            if is_well_being_query(analysis.cleaned_query):
                async for token in self._chat_service.stream_freeform(analysis.cleaned_query, history, request.voice_mode):
                    yield {"type": "token", "content": token}
                    answer_chunks.append(token)
            else:
                # Platform content query check
                knowledge_results = self._vector_store.search_knowledge(analysis.cleaned_query, top_k=2)
                is_platform_query = any(word in analysis.cleaned_query.lower() for word in [
                    "trvios", "partner", "split bills", "calculator", "app", "website", "platform", "booking", "cancel", "refund",
                    "about", "who are you", "what are you", "yourself", "help", "support", "contact", "email", "address", "hq",
                    "office", "headquarter", "founder", "owner", "started", "founded", "company", "team", "mission", "vision",
                    "value", "price", "guarantee", "reschedule", "modify", "policy", "fees", "guide", "operator", "host",
                    "portal", "community", "departure", "group", "solo", "motorcycle", "bike", "ride", "rafting", "camp",
                    "trek", "blog", "itinerary", "generator", "bot", "assistant"
                ])
                if knowledge_results and (is_platform_query or any(res.score > 0.15 for res in knowledge_results)):
                    async for token in self._chat_service.stream_answer(analysis.cleaned_query, [], knowledge_results, request.voice_mode):
                        yield {"type": "token", "content": token}
                        answer_chunks.append(token)
                else:
                    async for token in self._chat_service.stream_freeform(analysis.cleaned_query, history, request.voice_mode):
                        yield {"type": "token", "content": token}
                        answer_chunks.append(token)

        full_answer = "".join(answer_chunks)

        # 5. Context & Memory updates
        self._memory_manager.add_message(session_id, "user", request.query)
        self._memory_manager.add_message(session_id, "assistant", full_answer)

        # 6. Response Validation Layer (Safety & Hallucination check)
        is_safe_response = await self._safety_service.is_safe(full_answer)
        
        # Simple hallucination check
        hallucinated = False
        if sources:
            all_trips = self._trip_repo.get_all()
            valid_ids = {t.id for t in all_trips}
            for source in sources:
                if source.id not in valid_ids:
                    hallucinated = True
                    break

        yield {
            "type": "done",
            "query": request.query,
            "sources": [
                {"id": s.id, "title": s.title, "destination": s.destination, "score": s.score}
                for s in sources
            ],
            "validation": {
                "safety_ok": is_safe_response,
                "hallucination_flagged": hallucinated,
            }
        }

    async def _extract_preferences(self, query: str, history: list[dict[str, str]]) -> dict[str, Any]:
        """Use LLM to extract the 10 itinerary preference slots from user query and history."""
        history_context = ""
        if history:
            history_context = "\nConversation History:\n" + "\n".join(
                f"{msg['role']}: {msg['content']}" for msg in history[-5:]
            )

        prompt = (
            "You are a precise travel preference extractor. Extract the destination, duration_days (integer), "
            "and user choices for the following slots from the user query and conversation history:\n"
            f"User Query: \"{query}\"\n"
            f"{history_context}\n\n"
            "Output a JSON object with these keys and constraints:\n"
            "{\n"
            "  \"destination\": \"city name or region (string or null)\",\n"
            "  \"duration_days\": \"number of days (integer or null)\",\n"
            "  \"travel_type\": \"Solo\" | \"Couple\" | \"Family\" | \"Friends\" | null,\n"
            "  \"style\": \"Relaxed\" | \"Balanced\" | \"Active\" | \"Adventure\" | null,\n"
            "  \"mood\": \"Romantic\" | \"Nature\" | \"Fun\" | \"Peaceful\" | \"Photography\" | null,\n"
            "  \"budget\": \"Budget\" | \"Mid-range\" | \"Luxury\" | null,\n"
            "  \"transport\": \"Cab\" | \"Bike\" | \"Self-drive\" | \"Walking\" | null,\n"
            "  \"stay\": \"Hotel\" | \"Resort\" | \"Homestay\" | null,\n"
            "  \"food\": \"Veg\" | \"Non-Veg\" | \"Cafés\" | \"Local Cuisine\" | null,\n"
            "  \"activity\": \"Sightseeing\" | \"Adventure\" | \"Shopping\" | \"Temples\" | \"Waterfalls\" | \"Cafés\" | null\n"
            "}\n"
            "Output JSON only."
        )

        try:
            client = self._intent_ner_service._client
            if not client:
                return {}
            response = await client.chat.completions.create(
                model=self._intent_ner_service._model,
                messages=[
                    {"role": "system", "content": "You are a precise JSON extractor API."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.0,
            )
            import json
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            logger.warning(f"Error extracting travel preferences: {e}")
            return {}
