"""Intent detection and NER service implementation using OpenAI."""

import json
import re
from dataclasses import dataclass, field
from typing import Any
from openai import AsyncOpenAI
from clean_app.infrastructure.config.settings import Settings
from clean_app.infrastructure.config.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ParsedEntities:
    """Entities extracted from user query."""
    destination: str | None = None
    min_budget: float | None = None
    max_budget: float | None = None
    duration_days: int | None = None
    activities: list[str] = field(default_factory=list)
    trip_id: str | None = None
    # Optimized entities
    budget_level: str | None = "Medium"  # Low, Medium, High
    couple: bool = False
    mood: str | None = None
    weather: str | None = None
    occasion: str | None = None
    sort_by_cheapest: bool = False


@dataclass
class IntentNERResult:
    """Result containing classification and parsed values."""
    intent: str  # ITINERARY, HOTEL_SEARCH, RESTAURANT_SEARCH, WEATHER, BOOKING, PRICE_QUERY, SPLIT_BILL, GENERAL_QNA
    cleaned_query: str
    language: str
    entities: ParsedEntities


def is_well_being_query(query: str) -> bool:
    """Detect if the query expresses personal feelings, sadness, illness, or general discomfort."""
    q = query.lower()
    keywords = [
        "not well", "feel sad", "feeling sad", "sadness", "depressed", "depression", 
        "feel sick", "feeling sick", "unwell", "ill", "bad day", "tired", 
        "stressed", "feeling stressed", "anxious", "lonely", "down in the dumps",
        "hurt", "pain", "exhausted", "fatigued"
    ]
    return any(kw in q for kw in keywords)


def preprocess_text(text: str) -> str:
    """Remove punctuation and normalize text for optimal intent detection."""
    # Convert to lowercase
    text = text.lower()
    # Remove punctuation
    text = re.sub(r"[^\w\s]", "", text)
    # Normalize multiple spaces/newlines to single space
    text = re.sub(r"\s+", " ", text).strip()
    return text


class IntentNERService:
    """Classifies user queries and extracts key travel entities."""

    def __init__(self, settings: Settings) -> None:
        if settings.openai_api_key:
            self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        else:
            self._client = None
        self._model = settings.openai_model

    async def analyze_query(self, query: str, conversation_history: list[dict[str, str]] = None) -> IntentNERResult:
        """Analyze query to find intent and extract entities, incorporating history for context."""
        cleaned_query = preprocess_text(query)

        history_context = ""
        if conversation_history:
            history_context = "\nConversation History:\n" + "\n".join(
                f"{msg['role']}: {msg['content']}" for msg in conversation_history[-4:]
            )

        prompt = (
            "Analyze the following preprocessed user query for travel booking/planning and output a JSON object. "
            "Detect the user's intent and extract entities. Consider conversation history if helpful.\n"
            f"Preprocessed Query: \"{cleaned_query}\"\n"
            f"{history_context}\n\n"
            "The JSON output MUST follow this schema:\n"
            "{\n"
            "  \"intent\": \"ITINERARY\" | \"ITINERARY_MODIFY\" | \"TRIP_RECOMMENDATION\" | \"WEATHER_BASED_TRIP\" | \"MOOD_BASED_TRIP\" | \"HOTEL_SEARCH\" | \"RESTAURANT_SEARCH\" | \"WEATHER\" | \"BOOKING\" | \"PRICE_QUERY\" | \"SPLIT_BILL\" | \"GENERAL_QNA\" | \"LIST_TRIPS\",\n"
            "  \"cleaned_query\": \"spell-corrected and finalized query string\",\n"
            "  \"language\": \"detected language code, e.g. 'en', 'hi'\",\n"
            "  \"entities\": {\n"
            "    \"destination\": \"city, state, region, or country (string, or null if none)\",\n"
            "    \"min_budget\": \"minimum budget numeric value if mentioned (float, or null)\",\n"
            "    \"max_budget\": \"maximum budget numeric value if mentioned (float, or null)\",\n"
            "    \"duration_days\": \"duration of trip in days if mentioned (integer, or null)\",\n"
            "    \"activities\": [\"list of activities or tags mentioned, e.g. ['hiking', 'relaxing']\"],\n"
            "    \"trip_id\": \"referenced trip ID or index if mentioned (string, or null)\",\n"
            "    \"budget_level\": \"budget level preference: 'Low' | 'Medium' | 'High' (defaults to 'Medium')\",\n"
            "    \"couple\": \"boolean indicating if the query references traveling as a couple/pair (true/false, defaults to false)\",\n"
            "    \"mood\": \"trip mood / vibe: 'feeling low' | 'romantic' | 'excited' | 'stressed' | 'peaceful' | 'adventure' | 'relaxation' | null\",\n"
            "    \"weather\": \"trip weather/climate preference: 'rainy' | 'sunny' | 'snow' | 'cold' | 'hot' | null\",\n"
            "    \"occasion\": \"trip occasion: 'weekend' | 'honeymoon' | 'family' | 'solo' | 'friends' | 'couple' | null\",\n"
            "    \"sort_by_cheapest\": \"boolean indicating if the query is seeking the cheapest, lowest cost, or most affordable trips (true/false, defaults to false)\"\n"
            "  }\n"
            "}\n\n"
            "Intent guidelines:\n"
            "- ITINERARY: User wants to generate, schedule, or view a multi-day travel plan or schedule for a SPECIFIC destination (e.g., 'plan a 3-day trip to Manali', 'let's go to Shimla').\n"
            "- ITINERARY_MODIFY: User wants to edit, swap, customize, change, insert, or delete items/activities/stops in an existing itinerary (e.g., 'replace hotel X with Y', 'remove attraction A', 'add dinner at Z').\n"
            "- TRIP_RECOMMENDATION: User wants travel recommendations or destination suggestions without a specific weather or mood context (e.g. 'suggest a weekend getaway', 'recommend a trip').\n"
            "- WEATHER_BASED_TRIP: User wants suggestions based on weather/climate (e.g. 'places with snow', 'sunny beach trips').\n"
            "- MOOD_BASED_TRIP: User wants suggestions based on their feelings or emotional state (e.g. 'I am feeling low, recommend a trip', 'stressed', 'romantic trip').\n"
            "- HOTEL_SEARCH: User is searching for hotels, lodging, resorts, or home-stay accommodation options.\n"
            "- RESTAURANT_SEARCH: User is looking for dining, food places, cafes, or restaurant recommendations.\n"
            "- WEATHER: User is inquiring about the weather forecast or current climate condition of a place.\n"
            "- BOOKING: User wants to register, book, purchase, or reserve a package.\n"
            "- PRICE_QUERY: User is asking about prices, package costs, budget fits, or searching for packages by mood/tag/activity (e.g. 'trips under 20000', 'nature trips', 'romantic packages', 'adventure tours').\n"
            "- SPLIT_BILL: User wants to calculate split bills, group expenses, or use the calculator.\n"
            "- LIST_TRIPS: User wants to see a list of all available travel packages or trips (e.g., 'list all trips', 'show me all packages', 'what trips do you have').\n"
            "- GENERAL_QNA: Greetings, off-topic small talk, or platform knowledge/features."
        )

        try:
            if not self._client:
                raise RuntimeError("OpenAI client not configured")
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a precise Natural Language Understanding API. Output JSON only."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.0,
            )

            raw_content = response.choices[0].message.content
            parsed = json.loads(raw_content)

            ent_dict = parsed.get("entities", {})

            def _safe_float(val: Any) -> float | None:
                if val is None:
                    return None
                try:
                    return float(val)
                except (ValueError, TypeError):
                    return None

            def _safe_int(val: Any) -> int | None:
                if val is None:
                    return None
                try:
                    return int(val)
                except (ValueError, TypeError):
                    return None

            entities = ParsedEntities(
                destination=ent_dict.get("destination"),
                min_budget=_safe_float(ent_dict.get("min_budget")),
                max_budget=_safe_float(ent_dict.get("max_budget")),
                duration_days=_safe_int(ent_dict.get("duration_days")),
                activities=list(ent_dict.get("activities", [])),
                trip_id=str(ent_dict.get("trip_id")) if ent_dict.get("trip_id") is not None else None,
                budget_level=ent_dict.get("budget_level", "Medium"),
                couple=bool(ent_dict.get("couple", False)),
                mood=ent_dict.get("mood"),
                weather=ent_dict.get("weather"),
                occasion=ent_dict.get("occasion"),
                sort_by_cheapest=bool(ent_dict.get("sort_by_cheapest", False)),
            )

            return IntentNERResult(
                intent=parsed.get("intent", "GENERAL_QNA"),
                cleaned_query=parsed.get("cleaned_query", cleaned_query),
                language=parsed.get("language", "en"),
                entities=entities,
            )

        except Exception as e:
            # Only define cleaned_query if not already bound from try block
            try:
                c_query = cleaned_query
            except NameError:
                c_query = preprocess_text(query)
            
            logger.warning(f"Using rule-based NLU fallback: {e}")
            # Rule-based fallback classification
            fallback_intent = "SMALL_TALK"
            
            # Simple keyword matching for fallbacks
            low_query = c_query.lower()
            
            detected_mood = None
            mood_kws = ["romantic", "nature", "fun", "peaceful", "photography", "adventure", "wellness", "relaxation", "beach", "hiking", "safari"]
            for kw in mood_kws:
                if kw in low_query:
                    detected_mood = kw
                    break

            if any(w in low_query for w in ["replace", "swap", "remove stop", "attraction swap", "hotel change", "substitute"]):
                fallback_intent = "ITINERARY_MODIFY"
            elif any(w in low_query for w in ["list all", "show all", "all trips", "list trips", "show trips", "get all trips", "every trip"]):
                fallback_intent = "LIST_TRIPS"
            elif any(w in low_query for w in ["suggest", "recommend", "options", "popular", "where to", "getaway", "destinations"]):
                fallback_intent = "TRIP_RECOMMENDATION"
            elif "itinerary" in low_query or "plan" in low_query or "trip to" in low_query or "days in" in low_query:
                fallback_intent = "ITINERARY"
            elif "hotel" in low_query or "stay" in low_query or "resort" in low_query or "accommodation" in low_query:
                fallback_intent = "HOTEL_SEARCH"
            elif "restaurant" in low_query or "food" in low_query or "eat" in low_query or "cafe" in low_query or "dining" in low_query:
                fallback_intent = "RESTAURANT_SEARCH"
            elif "weather" in low_query or "forecast" in low_query or "temperature" in low_query or "climate" in low_query:
                fallback_intent = "WEATHER"
            elif "book" in low_query or "reserve" in low_query:
                fallback_intent = "BOOKING"
            elif any(w in low_query for w in ["price", "cost", "budget", "under", "inr", "affordable", "cheap"]) or detected_mood is not None:
                fallback_intent = "PRICE_QUERY"
            elif "split" in low_query or "bill" in low_query or "expense" in low_query or "calculator" in low_query:
                fallback_intent = "SPLIT_BILL"
            elif is_well_being_query(c_query):
                fallback_intent = "WELL_BEING"

            # Fallback NLU parser for entities:
            import re
            
            min_budget = None
            max_budget = None
            
            # budget keywords extraction
            num_pattern = r'(\d+(?:\.\d+)?)\s*(k)?'
            under_match = re.search(
                r'(?:under|below|less than|max|maximum|budget|price|<|<=)\s*(?:budget\s*)?(?:price\s*)?(?:₹|rs\.?|rupees?)?\s*' + num_pattern,
                low_query
            )
            above_match = re.search(
                r'(?:above|over|greater than|more than|min|minimum|>|>=)\s*(?:budget\s*)?(?:price\s*)?(?:₹|rs\.?|rupees?)?\s*' + num_pattern,
                low_query
            )
            
            if under_match:
                val = float(under_match.group(1))
                if under_match.group(2):  # 'k' suffix
                    val *= 1000
                max_budget = val
            if above_match:
                val = float(above_match.group(1))
                if above_match.group(2):  # 'k' suffix
                    val *= 1000
                min_budget = val

            # extract destination
            detected_dest = None
            destinations = [
                "manali", "udaipur", "goa", "shimla", "varanasi", "rishikesh", 
                "agra", "munnar", "ooty", "ladakh", "alleppey", "sikkim", "jaipur"
            ]
            for dest in destinations:
                if dest in low_query:
                    detected_dest = dest.title()
                    break

            # extract duration_days
            duration_match = re.search(r'(\d+)\s*(?:day|night|night\s*day)', low_query)
            duration_days = int(duration_match.group(1)) if duration_match else None

            # extract activities
            detected_activities = []
            activities_kws = ["hiking", "trekking", "culture", "heritage", "beach", "adventure", "snow", "camping"]
            for act in activities_kws:
                if act in low_query:
                    detected_activities.append(act)

            sort_by_cheapest = any(w in low_query for w in ["cheapest", "lowest price", "least expensive", "lowest cost", "most affordable"])

            parsed_fallback_entities = ParsedEntities(
                destination=detected_dest,
                min_budget=min_budget,
                max_budget=max_budget,
                duration_days=duration_days,
                activities=detected_activities,
                mood=detected_mood,
                sort_by_cheapest=sort_by_cheapest,
            )

            return IntentNERResult(
                intent=fallback_intent,
                cleaned_query=c_query,
                language="en",
                entities=parsed_fallback_entities,
            )
