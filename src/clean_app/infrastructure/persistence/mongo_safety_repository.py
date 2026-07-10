"""MongoDB repository for content safety, rate limiting, and temporary blocking tracking."""

import json
import datetime
from pathlib import Path
from typing import Any
from clean_app.infrastructure.config.settings import Settings

try:
    from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection
    from pymongo import ReturnDocument
    MOTOR_AVAILABLE = True
except ImportError:
    MOTOR_AVAILABLE = False
    # Stub definition for environment safety
    class ReturnDocument:
        AFTER = True
        BEFORE = False


class MongoSafetyRepository:
    """Manages safety status, rate limiting windows, and user blocks (with persistent in-memory fallback)."""

    def __init__(self, settings: Settings) -> None:
        self._fallback_file = Path(".safety_fallback_state.json")
        # Load fallback state from ignored hidden file to survive reloads
        self._load_fallback_state(settings)

        self._enabled = MOTOR_AVAILABLE
        if self._enabled:
            try:
                # Set a short server selection and connection timeout (2.0s) so we fail fast if DB is down
                self._client = AsyncIOMotorClient(
                    settings.mongodb_uri,
                    serverSelectionTimeoutMS=2000,
                    connectTimeoutMS=2000
                )
                self._db = self._client[settings.mongodb_db_name]
                self._users = self._db["users"]
                self._config = self._db["config"]
            except Exception as e:
                print(f"Failed to initialize MongoDB client: {e}. Falling back to in-memory safety checks.")
                self._enabled = False

        if not self._enabled:
            print("WARNING: 'motor' module not found or MongoDB connection failed. Falling back to in-memory safety repository.")

    def _load_fallback_state(self, settings: Settings) -> None:
        """Load in-memory fallback state from ignored hidden file to survive reloads."""
        self._users_mem: dict[str, dict[str, Any]] = {}
        self._config_mem: dict[str, Any] = {
            "spam_limit": settings.spam_limit,
            "block_duration_hours": settings.block_duration_hours,
            "rate_limit_requests": settings.rate_limit_requests,
            "rate_limit_window_seconds": settings.rate_limit_window_seconds,
        }

        if not self._fallback_file.exists():
            return

        try:
            with open(self._fallback_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            self._config_mem.update(data.get("config", {}))

            users_data = data.get("users", {})
            for user_key, doc in users_data.items():
                recent_reqs = []
                for t_str in doc.get("recent_requests", []):
                    try:
                        recent_reqs.append(datetime.datetime.fromisoformat(t_str))
                    except Exception:
                        pass

                blocked_until = None
                blocked_str = doc.get("blocked_until")
                if blocked_str:
                    try:
                        blocked_until = datetime.datetime.fromisoformat(blocked_str)
                    except Exception:
                        pass

                self._users_mem[user_key] = {
                    "spam_count": doc.get("spam_count", 0),
                    "blocked_until": blocked_until,
                    "recent_requests": recent_reqs
                }
        except Exception as e:
            print(f"Failed to load safety fallback state: {e}")

    def _save_fallback_state(self) -> None:
        """Save fallback state to ignored hidden file (starts with dot to prevent Uvicorn reload)."""
        try:
            serialized_users = {}
            for user_key, doc in self._users_mem.items():
                serialized_users[user_key] = {
                    "spam_count": doc.get("spam_count", 0),
                    "blocked_until": doc["blocked_until"].isoformat() if doc.get("blocked_until") else None,
                    "recent_requests": [t.isoformat() for t in doc.get("recent_requests", [])]
                }

            data = {
                "config": self._config_mem,
                "users": serialized_users
            }

            with open(self._fallback_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Failed to save safety fallback state: {e}")

    async def get_dynamic_settings(self, settings: Settings) -> dict[str, Any]:
        """Fetch dynamic configuration settings from DB, fallback to Settings defaults."""
        if self._enabled:
            try:
                doc = await self._config.find_one({"_id": "global_config"})
                if not doc:
                    default_doc = {
                        "_id": "global_config",
                        "spam_limit": settings.spam_limit,
                        "block_duration_hours": settings.block_duration_hours,
                        "rate_limit_requests": settings.rate_limit_requests,
                        "rate_limit_window_seconds": settings.rate_limit_window_seconds,
                    }
                    await self._config.insert_one(default_doc)
                    return default_doc
                return dict(doc)
            except Exception as e:
                print(f"Failed to fetch dynamic settings from MongoDB: {e}. Switching to permanent in-memory fallback mode.")
                self._enabled = False

        return self._config_mem

    async def is_user_blocked(self, user_key: str) -> tuple[bool, datetime.datetime | None]:
        """Check if user is currently blocked.

        Returns (is_blocked, blocked_until).
        """
        if self._enabled:
            try:
                doc = await self._users.find_one({"_id": user_key})
                if not doc:
                    return False, None

                blocked_until = doc.get("blocked_until")
                if blocked_until:
                    # Ensure it has timezone info
                    if blocked_until.tzinfo is None:
                        blocked_until = blocked_until.replace(tzinfo=datetime.timezone.utc)
                    now = datetime.datetime.now(datetime.timezone.utc)
                    if now < blocked_until:
                        return True, blocked_until
                    else:
                        # Block expired, reset in background
                        await self._users.update_one(
                            {"_id": user_key},
                            {"$set": {"blocked_until": None}}
                        )
                return False, None
            except Exception as e:
                print(f"Failed to check user blocked status from MongoDB: {e}. Switching to permanent in-memory fallback mode.")
                self._enabled = False

        # In-memory check
        doc = self._users_mem.get(user_key)
        if not doc:
            return False, None

        blocked_until = doc.get("blocked_until")
        if blocked_until:
            if blocked_until.tzinfo is None:
                blocked_until = blocked_until.replace(tzinfo=datetime.timezone.utc)
            now = datetime.datetime.now(datetime.timezone.utc)
            if now < blocked_until:
                return True, blocked_until
            else:
                doc["blocked_until"] = None
                self._save_fallback_state()
        return False, None

    async def record_request_and_check_rate_limit(
        self, user_key: str, limit: int, window_seconds: int
    ) -> bool:
        """Record timestamp and check sliding-window rate limit.

        Returns True if allowed, False if limit exceeded.
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        cutoff = now - datetime.timedelta(seconds=window_seconds)

        if self._enabled:
            try:
                # Retrieve user record or create one, appending the current request timestamp
                doc = await self._users.find_one_and_update(
                    {"_id": user_key},
                    {
                        "$push": {"recent_requests": now},
                        "$setOnInsert": {"spam_count": 0, "blocked_until": None}
                    },
                    upsert=True,
                    return_document=ReturnDocument.AFTER
                )

                if not doc:
                    return True

                recent_requests = doc.get("recent_requests", [])
                # Filter requests in the sliding window
                valid_requests = []
                for r in recent_requests:
                    if r.tzinfo is None:
                        r = r.replace(tzinfo=datetime.timezone.utc)
                    if r > cutoff:
                        valid_requests.append(r)

                # Update document with filtered requests to clean up database space
                await self._users.update_one(
                    {"_id": user_key},
                    {"$set": {"recent_requests": valid_requests}}
                )

                # Check if count of requests exceeds limit (including the current request)
                return len(valid_requests) <= limit
            except Exception as e:
                print(f"Failed to record request and check rate limit from MongoDB: {e}. Switching to permanent in-memory fallback mode.")
                self._enabled = False

        # In-memory check
        if user_key not in self._users_mem:
            self._users_mem[user_key] = {"spam_count": 0, "blocked_until": None, "recent_requests": []}

        doc = self._users_mem[user_key]
        doc["recent_requests"].append(now)

        recent_requests = doc["recent_requests"]
        valid_requests = []
        for r in recent_requests:
            if r.tzinfo is None:
                r = r.replace(tzinfo=datetime.timezone.utc)
            if r > cutoff:
                valid_requests.append(r)

        doc["recent_requests"] = valid_requests
        self._save_fallback_state()
        return len(valid_requests) <= limit

    async def increment_spam_count(
        self, user_key: str, limit: int, block_hours: float
    ) -> tuple[int, bool, datetime.datetime | None]:
        """Increment user's spam count. If limit reached, temporarily block user.

        Returns (new_spam_count, is_blocked_now, blocked_until).
        """
        if self._enabled:
            try:
                doc = await self._users.find_one_and_update(
                    {"_id": user_key},
                    {"$inc": {"spam_count": 1}},
                    upsert=True,
                    return_document=ReturnDocument.AFTER
                )

                if not doc:
                    return 1, False, None

                spam_count = doc.get("spam_count", 0)
                if spam_count >= limit:
                    now = datetime.datetime.now(datetime.timezone.utc)
                    blocked_until = now + datetime.timedelta(hours=block_hours)
                    await self._users.update_one(
                        {"_id": user_key},
                        {"$set": {"blocked_until": blocked_until, "spam_count": 0}}
                    )
                    return spam_count, True, blocked_until

                return spam_count, False, None
            except Exception as e:
                print(f"Failed to increment spam count from MongoDB: {e}. Switching to permanent in-memory fallback mode.")
                self._enabled = False

        # In-memory check
        if user_key not in self._users_mem:
            self._users_mem[user_key] = {"spam_count": 0, "blocked_until": None, "recent_requests": []}

        doc = self._users_mem[user_key]
        doc["spam_count"] += 1
        spam_count = doc["spam_count"]

        if spam_count >= limit:
            now = datetime.datetime.now(datetime.timezone.utc)
            blocked_until = now + datetime.timedelta(hours=block_hours)
            doc["blocked_until"] = blocked_until
            doc["spam_count"] = 0
            self._save_fallback_state()
            return spam_count, True, blocked_until

        self._save_fallback_state()
        return spam_count, False, None

