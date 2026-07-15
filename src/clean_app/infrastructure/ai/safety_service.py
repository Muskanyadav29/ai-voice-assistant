"""Content safety, spam detection, and moderation service implementation using OpenAI."""

import re
import asyncio
from typing import Any
from openai import AsyncOpenAI
from clean_app.infrastructure.config.settings import Settings

# Match 5 or more consecutively repeated characters (e.g. Aaaaaaaa)
REPEATED_CHARS_PATTERN = re.compile(r"(.)\1{4,}", re.IGNORECASE)

# Fast local check for threats, fraud, and illegal queries
SUSPICIOUS_PATTERN = re.compile(
    r"\b(otp|password|credit\s*card|visa\s*card|cvv|pin|card\s*detail|hack|phish|"
    r"drugs|weed|cocaine|heroin|marijuana|kill|murder|death|bomb|weapon|gun|"
    r"poison|threat|shoot|attack|illegal|scam|fraud|extort)\b",
    re.IGNORECASE
)


class SafetyService:
    """Uses heuristics, OpenAI Moderation, and LLM classification to moderate inputs for safety compliance."""

    def __init__(self, settings: Settings) -> None:
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        self._model = settings.openai_model or "gpt-4o-mini"

    def _check_heuristics(self, text: str) -> tuple[bool, str]:
        """Perform fast local heuristic checks for spam, repeated characters, and emoji spam."""
        trimmed = text.strip()
        if not trimmed:
            return True, ""

        # 1. Emoji spam check (run first so emoji spam is categorized as emoji spam, not repeated char spam)
        emoji_count = 0
        for char in trimmed:
            o = ord(char)
            # Standard emoji unicode blocks
            if (
                (0x1F300 <= o <= 0x1F9FF)
                or (0x2600 <= o <= 0x27BF)
                or (0x1F000 <= o <= 0x1F0FF)
                or (0x1F600 <= o <= 0x1F64F)
                or (0x1F680 <= o <= 0x1F6FF)
                or (0x1F900 <= o <= 0x1F9FF)
            ):
                emoji_count += 1
        if emoji_count > 5:
            return False, "Emoji spam detected"

        # 2. Repeated character check (e.g. Aaaaaaaa)
        if REPEATED_CHARS_PATTERN.search(trimmed):
            return False, "Repeated character spam"

        cleaned_text = "".join(trimmed.split()).lower()
        if len(cleaned_text) > 6:
            for char in set(cleaned_text):
                if cleaned_text.count(char) / len(cleaned_text) > 0.5:
                    return False, "High character frequency spam"

        # 3. Keyboard mashing / Gibberish consonant cluster check (e.g. Gsshususjsjshdh, ababbaba)
        words = trimmed.split()
        vowels = set("aeiouAEIOU")
        consonants = set("bcdfghjklmnpqrstvwxyzBCDFGHJKLMNPQRSTVWXYZ")

        for word in words:
            # Keep letters only
            cleaned_word = "".join(c for c in word if c.isalpha())
            if not cleaned_word:
                continue

            # Heuristic for low letter variety (e.g. ababbaba -> unique chars: a, b -> length 8)
            if len(cleaned_word) > 5 and len(set(cleaned_word.lower())) <= 2:
                return False, "Keyboard mashing detected (low letter variety)"

            # Check for keyboard row sequences (e.g. qwertyuiop, asdfgh)
            keyboard_rows = ["qwertyuiop", "asdfghjkl", "zxcvbnm"]
            for row in keyboard_rows:
                for i in range(len(cleaned_word) - 4):
                    sub = cleaned_word[i:i+5].lower()
                    if sub in row or sub in row[::-1]:
                        return False, "Keyboard mashing detected (keyboard row sequence)"

            consec_consonants = 0
            max_consec_consonants = 0
            for char in cleaned_word:
                if char in consonants:
                    consec_consonants += 1
                    if consec_consonants > max_consec_consonants:
                        max_consec_consonants = consec_consonants
                else:
                    consec_consonants = 0

            if max_consec_consonants >= 5:
                return False, "Keyboard mashing detected (consonant cluster)"

            # Check low vowel ratio for longer words
            if len(cleaned_word) > 5:
                vowel_count = sum(1 for c in cleaned_word if c in vowels)
                if vowel_count / len(cleaned_word) < 0.15:
                    return False, "Keyboard mashing detected (vowel ratio too low)"

        # 4. Fast local suspicious keyword check (for threats, fraud, illegal requests)
        match = SUSPICIOUS_PATTERN.search(trimmed)
        if match:
            matched_term = match.group(1).lower()
            if matched_term in ["kill", "murder", "death", "bomb", "gun", "weapon", "shoot", "threat", "attack"]:
                return False, f"Threat pattern detected ('{matched_term}')"
            elif matched_term in ["otp", "password", "credit card", "visa card", "cvv", "pin", "card detail", "phish", "scam", "fraud", "extort"]:
                return False, f"Fraud pattern detected ('{matched_term}')"
            elif matched_term in ["drugs", "weed", "cocaine", "heroin", "marijuana", "illegal", "hack"]:
                return False, f"Illegal content pattern detected ('{matched_term}')"

        return True, ""

    async def check_safety(self, text: str) -> tuple[bool, str]:
        """Perform comprehensive safety validation.

        Checks local heuristics, OpenAI Moderation, and custom GPT classification.
        Returns (is_safe, reason).
        """
        if not text.strip():
            return True, ""

        # 1. Local fast heuristic checks (including keywords and low-variety gibberish)
        is_heuristic_safe, heuristic_reason = self._check_heuristics(text)
        if not is_heuristic_safe:
            return False, heuristic_reason

        # 2. OpenAI Moderation API (with 2.0s timeout to prevent hangs)
        try:
            mod_response = await asyncio.wait_for(
                self._client.moderations.create(input=text),
                timeout=2.0
            )
            if mod_response.results[0].flagged:
                flagged_categories = [
                    cat for cat, val in mod_response.results[0].categories.items() if val
                ]
                reason = f"Moderation violation: {', '.join(flagged_categories)}"
                return False, reason
        except asyncio.TimeoutError:
            print("Safety API Moderation call timed out. Proceeding to LLM safety evaluation.")
        except Exception as e:
            print(f"Safety API Moderation error: {e}")

        # 3. Custom LLM Check for remaining complex gibberish (with 2.0s timeout to prevent hangs)
        try:
            system_prompt = (
                "You are a strict moderation guard for a travel assistant chatbot.\n"
                "Analyze the user's message and determine if it violates safety guidelines.\n"
                "Specifically, flag if the message is:\n"
                "1. Threatening or harassing (e.g. death threats, blackmail, stalking).\n"
                "2. Fraudulent, scam-related, or financial exploit (e.g. phishing, credit card fraud, hacking accounts, buying fake reviews).\n"
                "3. Promoting or requesting illegal activities (e.g. buying illegal drugs, smuggling, passport forgery, weapons).\n"
                "4. Nonsensical gibberish or keyboard mashing (e.g. 'Bcdaahjsieiej') that contains no actual words in English, Hindi, or Hinglish. Note that brand/app names like 'trvios', 'trvios.com', and 'tara' are completely valid words and must never be classified as gibberish.\n\n"
                "Respond with EXACTLY 'SAFE' or 'UNSAFE: <reason>'. Do not include any other characters or commentary."
            )
            
            chat_response = await asyncio.wait_for(
                self._client.chat.completions.create(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": text}
                    ],
                    max_tokens=20,
                    temperature=0.0,
                ),
                timeout=2.0
            )
            result = chat_response.choices[0].message.content
            if result and result.upper().startswith("UNSAFE"):
                reason = result.split(":", 1)[1].strip() if ":" in result else "Safety check flagged"
                return False, reason
            return True, ""
        except asyncio.TimeoutError:
            print("Safety LLM evaluation call timed out. Failing open to ensure responsiveness.")
            return True, ""
        except Exception as e:
            print(f"Safety LLM evaluation error: {e}")
            return True, ""

    async def is_safe(self, text: str) -> bool:
        """Check if the given text is safe. Returns True if safe, False if flagged."""
        is_safe_flag, _ = await self.check_safety(text)
        return is_safe_flag


