"""Use case for modifying travel itineraries based on natural language instructions."""

from clean_app.infrastructure.ai.chat_service import ChatService


class ModifyItineraryUseCase:
    """Applies user-requested modifications (swaps, removals, insertions) to an itinerary."""

    def __init__(self, chat_service: ChatService) -> None:
        self._chat_service = chat_service

    async def execute(self, current_itinerary: str, instruction: str) -> str:
        """Modify the current itinerary structure based on the natural language instruction."""
        system_prompt = (
            "You are a helpful travel itinerary editor. "
            "Your job is to apply modifications to the provided itinerary following the user's instruction. "
            "You can replace attractions, swap hotels, add events, or remove stops. "
            "CRITICAL: Keep the output structure identical to the original itinerary structure. "
            "Preserve any markdown timeline format and any custom CARD or TRAVEL tags. "
            "Only edit the specific parts of the itinerary that the user requested to modify, and keep other elements unchanged."
        )
        user_prompt = (
            f"Current Itinerary:\n{current_itinerary}\n\n"
            f"Instruction to apply: {instruction}"
        )
        
        chunks = []
        async for token in self._chat_service.stream_custom_prompt(system_prompt, user_prompt, voice_mode=False):
            chunks.append(token)
            
        return "".join(chunks)
