"""Unit tests for safety heuristics, rate limiting, and temporary blocking logic."""

import sys
from unittest.mock import MagicMock

# Mock motor and pymongo modules if not installed so tests can load and run MongoDB test cases
if "motor" not in sys.modules:
    mock_motor = MagicMock()
    mock_motor_asyncio = MagicMock()
    sys.modules["motor"] = mock_motor
    sys.modules["motor.motor_asyncio"] = mock_motor_asyncio

if "pymongo" not in sys.modules:
    mock_pymongo = MagicMock()
    sys.modules["pymongo"] = mock_pymongo

import pytest
import datetime
from unittest.mock import AsyncMock, patch
from clean_app.infrastructure.config.settings import Settings
from clean_app.infrastructure.ai.safety_service import SafetyService
from clean_app.infrastructure.persistence.mongo_safety_repository import MongoSafetyRepository


# --- Test Safety Heuristics ---

def test_safety_service_heuristics_safe() -> None:
    settings = Settings(openai_api_key="mock_key")
    safety_service = SafetyService(settings)
    
    # Safe Hinglish and English queries
    safe_queries = [
        "Goa ka plan banana hai, budget 10k hai.",
        "Recommend some hotels in Udaipur.",
        "Mujhe nature trips pasand hain.",
        "Weather in Manali?",
    ]
    for q in safe_queries:
        is_safe, reason = safety_service._check_heuristics(q)
        assert is_safe, f"Query '{q}' should be safe, but failed: {reason}"


def test_safety_service_heuristics_repeated_chars() -> None:
    settings = Settings(openai_api_key="mock_key")
    safety_service = SafetyService(settings)
    
    # Repeated characters
    unsafe_queries = [
        "Aaaaaaaa",
        "helloooooo",
        "trip plan pppppp please",
    ]
    for q in unsafe_queries:
        is_safe, reason = safety_service._check_heuristics(q)
        assert not is_safe, f"Query '{q}' should be flagged for repeated characters"
        assert "repeated" in reason.lower() or "frequency" in reason.lower()


def test_safety_service_heuristics_keyboard_mashing() -> None:
    settings = Settings(openai_api_key="mock_key")
    safety_service = SafetyService(settings)
    
    # Keyboard mashing
    unsafe_queries = [
        "Gsshususjsjshdh",
        "qwertyuiopasdfg",
        "bcdfghjklmnp",
        "ababbaba",
    ]
    for q in unsafe_queries:
        is_safe, reason = safety_service._check_heuristics(q)
        assert not is_safe, f"Query '{q}' should be flagged for keyboard mashing"
        assert "keyboard" in reason.lower()


def test_safety_service_heuristics_emoji_spam() -> None:
    settings = Settings(openai_api_key="mock_key")
    safety_service = SafetyService(settings)
    
    # Emoji spam (>5 emojis)
    unsafe_queries = [
        "Goa trip plan 🚗✈️🌴🌊🏖️❤️",
        "🏨🏨🏨🏨🏨🏨",
    ]
    for q in unsafe_queries:
        is_safe, reason = safety_service._check_heuristics(q)
        assert not is_safe, f"Query '{q}' should be flagged for emoji spam"
        assert "emoji" in reason.lower()


def test_safety_service_heuristics_keywords() -> None:
    settings = Settings(openai_api_key="mock_key")
    safety_service = SafetyService(settings)
    
    # Threat, fraud, and illegal query patterns
    unsafe_queries = [
        "Give me your OTP",
        "I will kill everyone",
        "How can I buy illegal drugs?",
        "Help me hack this server",
    ]
    for q in unsafe_queries:
        is_safe, reason = safety_service._check_heuristics(q)
        assert not is_safe, f"Query '{q}' should be flagged by local keyword patterns"
        assert any(term in reason.lower() for term in ["threat", "fraud", "illegal"])



# --- Test Mongo Safety Repository Rate Limiter and Blocks ---

@pytest.mark.asyncio
async def test_mongo_safety_repository_is_blocked() -> None:
    settings = Settings(openai_api_key="mock_key")
    
    with patch("clean_app.infrastructure.persistence.mongo_safety_repository.AsyncIOMotorClient") as mock_client:
        mock_db = MagicMock()
        mock_users = AsyncMock()
        mock_client.return_value.__getitem__.return_value = mock_db
        mock_db.__getitem__.return_value = mock_users
        
        repo = MongoSafetyRepository(settings)
        repo._users = mock_users
        
        # Scenario 1: User doesn't exist
        mock_users.find_one.return_value = None
        is_blocked, blocked_until = await repo.is_user_blocked("user_1")
        assert not is_blocked
        assert blocked_until is None
        
        # Scenario 2: User blocked in the future
        future_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
        mock_users.find_one.return_value = {"_id": "user_1", "blocked_until": future_time}
        is_blocked, blocked_until = await repo.is_user_blocked("user_1")
        assert is_blocked
        assert blocked_until == future_time
        
        # Scenario 3: User block expired
        past_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)
        mock_users.find_one.return_value = {"_id": "user_1", "blocked_until": past_time}
        is_blocked, blocked_until = await repo.is_user_blocked("user_1")
        assert not is_blocked
        mock_users.update_one.assert_called_with(
            {"_id": "user_1"},
            {"$set": {"blocked_until": None}}
        )


@pytest.mark.asyncio
async def test_mongo_safety_repository_rate_limit() -> None:
    settings = Settings(openai_api_key="mock_key")
    
    with patch("clean_app.infrastructure.persistence.mongo_safety_repository.AsyncIOMotorClient") as mock_client:
        mock_db = MagicMock()
        mock_users = AsyncMock()
        mock_client.return_value.__getitem__.return_value = mock_db
        mock_db.__getitem__.return_value = mock_users
        
        repo = MongoSafetyRepository(settings)
        repo._users = mock_users
        
        now = datetime.datetime.now(datetime.timezone.utc)
        recent_reqs = [
            now - datetime.timedelta(seconds=10),
            now - datetime.timedelta(seconds=5),
            now,
        ]
        
        mock_users.find_one_and_update.return_value = {
            "_id": "user_1",
            "recent_requests": recent_reqs
        }
        
        # Under limit = 5, should be allowed
        allowed = await repo.record_request_and_check_rate_limit("user_1", limit=5, window_seconds=60)
        assert allowed
        
        # Under limit = 2, should be blocked
        allowed = await repo.record_request_and_check_rate_limit("user_1", limit=2, window_seconds=60)
        assert not allowed


@pytest.mark.asyncio
async def test_mongo_safety_repository_spam_increment() -> None:
    settings = Settings(openai_api_key="mock_key")
    
    with patch("clean_app.infrastructure.persistence.mongo_safety_repository.AsyncIOMotorClient") as mock_client:
        mock_db = MagicMock()
        mock_users = AsyncMock()
        mock_client.return_value.__getitem__.return_value = mock_db
        mock_db.__getitem__.return_value = mock_users
        
        repo = MongoSafetyRepository(settings)
        repo._users = mock_users
        
        # Scenario 1: Spam count under limit
        mock_users.find_one_and_update.return_value = {"_id": "user_1", "spam_count": 3}
        spam_count, is_blocked, blocked_until = await repo.increment_spam_count("user_1", limit=5, block_hours=48)
        assert spam_count == 3
        assert not is_blocked
        assert blocked_until is None
        
        # Scenario 2: Spam count hits limit
        mock_users.find_one_and_update.return_value = {"_id": "user_1", "spam_count": 5}
        spam_count, is_blocked, blocked_until = await repo.increment_spam_count("user_1", limit=5, block_hours=48)
        assert spam_count == 5
        assert is_blocked
        assert blocked_until is not None
        mock_users.update_one.assert_called()


@pytest.mark.asyncio
async def test_mongo_safety_repository_fallback() -> None:
    settings = Settings(openai_api_key="mock_key")
    repo = MongoSafetyRepository(settings)
    # Force disabled (in-memory fallback mode)
    repo._enabled = False
    repo._users_mem = {}

    # 1. Test in-memory block check
    is_blocked, _ = await repo.is_user_blocked("user_mem")
    assert not is_blocked

    # 2. Test in-memory rate limiting sliding window
    allowed = await repo.record_request_and_check_rate_limit("user_mem", limit=2, window_seconds=60)
    assert allowed
    allowed = await repo.record_request_and_check_rate_limit("user_mem", limit=2, window_seconds=60)
    assert allowed
    allowed = await repo.record_request_and_check_rate_limit("user_mem", limit=2, window_seconds=60)
    assert not allowed

    # 3. Test in-memory spam increment and blocking
    spam_count, is_blocked_now, blocked_until = await repo.increment_spam_count("user_mem", limit=3, block_hours=48)
    assert spam_count == 1
    assert not is_blocked_now

    spam_count, is_blocked_now, blocked_until = await repo.increment_spam_count("user_mem", limit=3, block_hours=48)
    assert spam_count == 2
    assert not is_blocked_now

    spam_count, is_blocked_now, blocked_until = await repo.increment_spam_count("user_mem", limit=3, block_hours=48)
    assert spam_count == 3
    assert is_blocked_now
    assert blocked_until is not None

