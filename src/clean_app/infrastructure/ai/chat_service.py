"""RAG chat service implementations."""

from collections.abc import AsyncIterator
import asyncio

from clean_app.application.use_cases.chat_with_trips import ChatService
from clean_app.domain.entities.trip import Trip
from clean_app.domain.repositories.vector_store import TripSearchResult, KnowledgeSearchResult
from clean_app.infrastructure.config.settings import Settings
from clean_app.infrastructure.config.logging import get_logger

logger = get_logger(__name__)


def _format_price(trip: Trip) -> str:
    if trip.currency == "INR":
        return f"₹{trip.price:.0f}"
    return f"${trip.price:.0f}"


def is_well_being_query(query: str) -> bool:
    """Helper to detect if a query is expressing personal feelings, illness, or sadness."""
    q = query.lower()
    keywords = [
        "not well", "feel sad", "feeling sad", "sadness", "depressed", "depression", 
        "feel sick", "feeling sick", "unwell", "ill", "bad day", "tired", 
        "stressed", "feeling stressed", "anxious", "lonely", "down in the dumps",
        "hurt", "pain", "exhausted", "fatigued"
    ]
    return any(kw in q for kw in keywords)


class TemplateChatService(ChatService):
    """Generate mock travel assistant answers without an external LLM."""

    async def generate_answer(
        self,
        query: str,
        results: list[TripSearchResult],
        knowledge_results: list[KnowledgeSearchResult] = None,
        voice_mode: bool = False,
    ) -> str:
        chunks = []
        async for chunk in self.stream_answer(query, results, knowledge_results, voice_mode):
            chunks.append(chunk)
        return "".join(chunks)

    async def stream_answer(
        self,
        query: str,
        results: list[TripSearchResult],
        knowledge_results: list[KnowledgeSearchResult] = None,
        voice_mode: bool = False,
    ) -> AsyncIterator[str]:
        if is_well_being_query(query):
            trip_info = ""
            if results:
                trip = results[0].trip
                trip_info = f" We offer peaceful trips like the {trip.title} to {trip.destination} for some relaxation."
            if voice_mode:
                response = (
                    f"I'm sorry to hear that you're not feeling well. Please take care of yourself!{trip_info} "
                    "Let me know if I can help you find relaxing getaways."
                )
            else:
                response = (
                    f"I'm really sorry to hear that you're not feeling well or feeling sad. Please take care of yourself!\n\n"
                    f"If you'd like to unwind, a change of scenery might help.{trip_info} "
                    "Let me know if you would like to search for more packages or detail any itineraries."
                )
            for word in response.split(" "):
                yield word + " "
                if not voice_mode:
                    await asyncio.sleep(0.02)
            return

        if not results:
            if knowledge_results:
                best_doc = knowledge_results[0].document
                if voice_mode:
                    response = f"Regarding our {best_doc.title}: {best_doc.content[:100]}. Let me know if you would like to search for packages."
                else:
                    response = (
                        f"Here is some information about Trvios in response to '{query}':\n\n"
                        f"**{best_doc.title}**\n{best_doc.content}\n\n"
                        "Let me know if you would also like to search for available trip packages!"
                    )
                for word in response.split(" "):
                    yield word + " "
                    if not voice_mode:
                        await asyncio.sleep(0.02)
                return

            response = (
                f"I searched our database for '{query}', but couldn't find any direct matches. "
                "Could you try widening your search or asking about destinations like Manali, "
                "Varanasi, Udaipur, or activities like hiking, snow adventures, and temple tours?"
            )
            for word in response.split(" "):
                yield word + " "
                if not voice_mode:
                    await asyncio.sleep(0.04)
            return

        if voice_mode:
            trip = results[0].trip
            response = (
                f"I found a great option: {trip.title} to {trip.destination} for {trip.duration_days} days, "
                f"priced at {_format_price(trip)}. Would you like me to tell you more about this package?"
            )
            for word in response.split(" "):
                yield word + " "
                if not voice_mode:
                    await asyncio.sleep(0.02)
            return

        # Build a beautiful, coherent travel agent narrative
        intro = (
            f"Hello! I found {len(results)} fantastic trip options matching your interest in '{query}'. "
            "Here are the details to help you plan your next journey:\n\n"
        )
        for word in intro.split(" "):
            yield word + " "
            if not voice_mode:
                await asyncio.sleep(0.02)

        for index, result in enumerate(results, start=1):
            trip = result.trip
            
            # Format highlights if available
            highlights_str = ""
            if trip.highlights:
                highlights_str = f" This tour features incredible experiences like " + ", ".join(trip.highlights[:3]) + "."

            # Format itinerary if available
            itinerary_str = ""
            if trip.itinerary:
                days_summary = []
                for item in trip.itinerary[:2]: # Show first 2 days
                    days_summary.append(f"Day {item.day} ({item.title}): {item.description}")
                if days_summary:
                    itinerary_str = "\n   - **Highlights of the plan:**\n     * " + "\n     * ".join(days_summary)
            
            item_text = (
                f"**{index}. {trip.title}** ({trip.destination}, {trip.country})\n"
                f"   - **Duration:** {trip.duration_days} Days | **Price:** {_format_price(trip)}\n"
                f"   - **Overview:** {trip.description}{highlights_str}{itinerary_str}\n\n"
            )
            
            # Yield word by word for streaming animation effect
            for word in item_text.split(" "):
                yield word + " "
                if not voice_mode:
                    await asyncio.sleep(0.02)
                
        closing = (
            "Would you like more details on any of these trips, "
            "such as the full day-by-day itinerary or booking information?"
        )
        for word in closing.split(" "):
            yield word + " "
            if not voice_mode:
                await asyncio.sleep(0.02)

    async def stream_freeform(
        self,
        query: str,
        conversation_history: list[dict[str, str]] = None,
        voice_mode: bool = False,
    ) -> AsyncIterator[str]:
        if is_well_being_query(query):
            if voice_mode:
                response = (
                    "I'm sorry to hear that you're not feeling well. Please take care of yourself! "
                    "If you would like to relax, I can recommend some calming travel packages like the Bali Wellness Retreat."
                )
            else:
                response = (
                    "I'm really sorry to hear that you're not feeling well or feeling sad. Please take care of yourself!\n\n"
                    "If you want to distract yourself or unwind, I'd recommend looking at some of our peaceful travel packages "
                    "like a wellness retreat or a nature getaway. Let me know if you would like me to find some calming trips for you."
                )
        else:
            if voice_mode:
                response = "Hello! I am your Trvios voice assistant. I can help find packages across all 28 states, detail itineraries, or book a trip using our RAG knowledge. How can I help you today?"
            else:
                response = (
                    "I am a travel chatbot for Trvios. To find packages or detail itineraries, "
                    "please ask me questions like 'show me trips under 20000 INR' or 'detail the Shimla itinerary'. "
                    "I can also help with platform inquiries like split bills, our refund policy, and homestay partner features."
                )
        for word in response.split(" "):
            yield word + " "
            if not voice_mode:
                await asyncio.sleep(0.04)

    async def stream_custom_prompt(
        self,
        system_prompt: str,
        user_prompt: str,
        voice_mode: bool = False,
    ) -> AsyncIterator[str]:
        dest = "your destination"
        for line in user_prompt.split("\n"):
            if line.startswith("Destination:"):
                dest = line.split(":", 1)[1].strip()
                break

        # Check if this is a Trip Recommendation prompt
        if "Recommend the best destinations" in system_prompt or "Matching Trip Database Packages:" in user_prompt or "Available Trip Packages" in user_prompt:
            trips_section = ""
            is_list_all = "Available Trip Packages" in user_prompt
            if "Matching Trip Database Packages:\n" in user_prompt:
                trips_section = user_prompt.split("Matching Trip Database Packages:\n", 1)[1].strip()
            elif "Available Trip Packages in Database:\n" in user_prompt:
                trips_section = user_prompt.split("Available Trip Packages in Database:\n", 1)[1].strip()
            
            if voice_mode:
                response = "Here are the available trip destinations. Which one would you like to plan an itinerary for?"
            else:
                header = "Here are all the available trip packages:" if is_list_all else "Here are the top trip recommendations based on your preferences:"
                response = (
                    "### Recommended Trips & Packages\n\n"
                    f"{header}\n\n"
                    f"{trips_section or '- Nature Retreat in Manali\n- Cultural Highlights of Udaipur\n- Beach Escape in Goa'}\n\n"
                    "Please tell me which destination you would like to generate a detailed day-wise itinerary for!"
                )
        elif "Itinerary" in system_prompt or "itinerary" in system_prompt:
            if voice_mode:
                response = f"Here is a custom 3-day itinerary for {dest} with great hotels, attractions, and local weather. Would you like me to book it?"
            else:
                response = (
                    f"### Customized Travel Guide & Itinerary: {dest.title()}\n\n"
                    f"This personalized itinerary is crafted for your style. Here is a summary of suggestions:\n"
                    f"- **Stay**: We recommend top rated local stays.\n"
                    f"- **Attractions**: Visit local sights and popular places.\n"
                    f"- **Dining**: Enjoy local cuisine at top rated restaurants.\n\n"
                    f"Let me know if you would like to book a verified tour package!"
                )
        elif "hotel" in system_prompt.lower():
            response = f"Here are the top hotels recommendations for {dest}."
        elif "restaurant" in system_prompt.lower():
            response = f"Here are the top restaurants recommendations for {dest}."
        elif "weather" in system_prompt.lower():
            response = f"The current weather forecast for {dest} is pleasant."
        else:
            response = "I have processed your query and formulated a customized response."

        for word in response.split(" "):
            yield word + " "
            if not voice_mode:
                await asyncio.sleep(0.02)



class OpenAIChatService(ChatService):
    """Generate answers using OpenAI when an API key is configured."""

    def __init__(self, settings: Settings) -> None:
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        self._model = settings.openai_model

    async def generate_answer(
        self,
        query: str,
        results: list[TripSearchResult],
        knowledge_results: list[KnowledgeSearchResult] = None,
        voice_mode: bool = False,
    ) -> str:
        chunks = []
        async for chunk in self.stream_answer(query, results, knowledge_results, voice_mode):
            chunks.append(chunk)
        return "".join(chunks)

    async def stream_answer(
        self,
        query: str,
        results: list[TripSearchResult],
        knowledge_results: list[KnowledgeSearchResult] = None,
        voice_mode: bool = False,
    ) -> AsyncIterator[str]:
        if not results and not knowledge_results:
            async for token in TemplateChatService().stream_answer(query, results, knowledge_results, voice_mode):
                yield token
            return

        context_blocks = []
        for result in results:
            trip = result.trip
            itinerary_parts = []
            for item in trip.itinerary:
                act_str = ", ".join(item.activities)
                itinerary_parts.append(
                    f"  * Day {item.day}: {item.title} - {item.description} "
                    f"(Activities: {act_str} at {item.formatted_address})"
                )
            itinerary_context = "\n".join(itinerary_parts)
            highlights_context = ", ".join(trip.highlights)
            
            context_blocks.append(
                f"Trip ID: {trip.id}\n"
                f"Title: {trip.title}\n"
                f"Destination: {trip.destination}, {trip.country}\n"
                f"Duration: {trip.duration_days} days\n"
                f"Price: {_format_price(trip)}\n"
                f"Tags: {', '.join(trip.tags)}\n"
                f"Highlights: {highlights_context}\n"
                f"Description: {trip.description}\n"
                f"Itinerary:\n{itinerary_context}\n"
            )
        trip_context = "\n---\n".join(context_blocks) if context_blocks else "No matching trips found."

        knowledge_blocks = []
        if knowledge_results:
            for kr in knowledge_results:
                doc = kr.document
                knowledge_blocks.append(
                    f"Page Title: {doc.title}\n"
                    f"Page URL: {doc.url}\n"
                    f"Content Details: {doc.content}"
                )
        knowledge_context = "\n---\n".join(knowledge_blocks) if knowledge_blocks else "No platform knowledge pages found."

        if voice_mode:
            # Check if this is a platform feature/sitemap query
            is_platform_query = any(word in query.lower() for word in [
                "trvios", "partner", "split bills", "calculator", "app", "website", "platform", "booking", "cancel", "refund",
                "about", "who are you", "what are you", "yourself", "help", "support", "contact"
            ])
            if is_platform_query or (knowledge_results and len(knowledge_results) > 0):
                system_prompt = (
                    "You are TARA, a warm, professional travel concierge for Trvios (similar to Ixigo's voice assistant). Answering over a two-way voice call. "
                    "CRITICAL: Always respond in the same language and style (English, Hindi, or Hinglish/Indian English) as the user's query. "
                    "The user is asking about the Trvios.com platform, its features, tools, or policies. "
                    "Answer using ONLY the provided platform knowledge contexts. "
                    "CRITICAL: Keep your response clear, structured, and under 80 words. Explain the features using "
                    "spoken numbers like 'First...', 'Second...' instead of markdown lists or bullet points. "
                    "Do NOT use markdown bold/italic asterisks or hashes, as the user is listening to your voice. "
                    "Provide a clear, easy-to-understand explanation so that the user isn't confused."
                )
            else:
                system_prompt = (
                    "You are TARA, a warm, professional travel concierge for Trvios (similar to Ixigo's voice assistant). Answering over a two-way voice call. "
                    "CRITICAL: Always respond in the same language and style (English, Hindi, or Hinglish/Indian English) as the user's query. "
                    "If the user is expressing personal feelings, sadness, or physical/emotional discomfort, "
                    "first respond with genuine empathy and comfort, then suggest a calming or peaceful package from "
                    "the context that could help them relax. "
                    "Otherwise, answer using ONLY the contexts provided. "
                    "CRITICAL: Keep your response extremely concise: 1 or 2 sentences max (under 40 words) "
                    "in plain conversational text. Do NOT use bullet points, lists, or markdown formatting (like asterisks or hashes), "
                    "as the user is listening to your voice."
                )
        else:
            system_prompt = (
                "You are a helpful travel assistant for Trvios, a technology-driven travel marketplace in India. "
                "If the user is expressing personal feelings, sadness, or physical/emotional discomfort, "
                "respond with warmth, genuine empathy, and comfort. Suggest relaxing or wellness packages "
                "from the provided context (like yoga, spa, beach, or nature retreats) that could help them unwind. "
                "Otherwise, answer using ONLY the trip and platform knowledge contexts provided below. "
                "Citing the specific trip names or website pages is encouraged. "
                "If the context does not contain enough information to answer, state this clearly and "
                "guide the user to ask about Trvios features, packages, bookings, or support."
            )

        user_content = (
            f"Trip Context:\n{trip_context}\n\n"
            f"Platform Knowledge Context:\n{knowledge_context}\n\n"
            f"User question: {query}"
        )

        try:
            stream = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {
                        "role": "user",
                        "content": user_content,
                    },
                ],
                temperature=0.3,
                stream=True,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
        except Exception as e:
            logger.error(f"OpenAI chat completion failed: {e}. Falling back to TemplateChatService...", exc_info=True)
            async for token in TemplateChatService().stream_answer(query, results, knowledge_results, voice_mode):
                yield token

    async def stream_freeform(
        self,
        query: str,
        conversation_history: list[dict[str, str]] = None,
        voice_mode: bool = False,
    ) -> AsyncIterator[str]:
        if voice_mode:
            system_instruction = (
                "You are TARA, a friendly and premium travel concierge on a two-way voice call for Trvios (similar to Ixigo's assistant). "
                "Trvios offers verified tour packages across all 28 states of India, weekend getaways, adventure trips, bike rides, "
                "Holi/Hornbill festival tours, an AI itinerary generator, homestay partner portals, and group split bills tools. "
                "CRITICAL: Always respond in the same language and style (English, Hindi, or Hinglish/Indian English) as the user's query. "
                "If the user is expressing personal feelings, sadness, illness, or discomfort, respond with genuine warmth, comfort, and empathy. "
                "CRITICAL: Keep your response extremely concise: 1 or 2 sentences max (under 30 words) "
                "in plain conversational text. Do NOT use markdown, bullet points, or list formatting."
            )
        else:
            system_instruction = (
                "You are a friendly and premium travel chatbot for Trvios, a technology-driven travel marketplace in India. "
                "Trvios offers verified tour packages across all 28 states of India, weekend getaways, adventure trips, bike rides, "
                "Holi/Hornbill festival tours, an AI itinerary generator, homestay partner portals, and group split bills tools. "
                "You can chat about anything related to trips, destinations, general travel advice, packing lists, or greetings. "
                "If the user is expressing personal feelings, sadness, illness, or discomfort, respond with genuine warmth, comfort, and empathy. "
                "Be helpful and concise. Keep responses under 3 paragraphs."
            )
        messages = [
            {
                "role": "system",
                "content": system_instruction,
            }
        ]
        if conversation_history:
            for turn in conversation_history:
                messages.append({"role": turn["role"], "content": turn["content"]})
        
        messages.append({"role": "user", "content": query})

        try:
            stream = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=0.7,
                stream=True,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
        except Exception as e:
            logger.error(f"Error in free-form LLM stream: {e}. Falling back to TemplateChatService...", exc_info=True)
            async for token in TemplateChatService().stream_freeform(query, conversation_history, voice_mode):
                yield token

    async def stream_custom_prompt(
        self,
        system_prompt: str,
        user_prompt: str,
        voice_mode: bool = False,
    ) -> AsyncIterator[str]:
        try:
            stream = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                stream=True,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
        except Exception as e:
            logger.error(f"OpenAI custom prompt failed: {e}. Falling back to TemplateChatService...", exc_info=True)
            async for token in TemplateChatService().stream_custom_prompt(system_prompt, user_prompt, voice_mode):
                yield token


def build_chat_service(settings: Settings) -> ChatService:
    """Pick the best available chat backend."""
    if settings.openai_api_key:
        return OpenAIChatService(settings)
    return TemplateChatService()
