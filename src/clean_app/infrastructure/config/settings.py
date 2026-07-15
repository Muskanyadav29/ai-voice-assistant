"""Application configuration."""

import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
@dataclass(frozen=True, slots=True)
class Settings:
    """Application settings loaded from environment."""

    app_env: str = "development"
    app_debug: bool = False
    database_url: str = "sqlite:///./app.db"
    chroma_persist_dir: str = "./data/chroma"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    auto_index_trips: bool = True
    trvios_trips_api_url: str = "https://api.trvios.com/api/ai/trips"
    trip_source: str = "trvios"
    sarvam_api_key: str | None = None
    trvios_api_key: str | None = None
    google_places_api_key: str = "AIzaSyCcJn4CxZmLGoNXB2G10XV2N4K_gqRK6ww"
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "trip_chat"
    spam_limit: int = 10
    block_duration_hours: int = 48
    rate_limit_requests: int = 30
    rate_limit_window_seconds: int = 60
    ollama_model: str = "llama3.2"


    @classmethod
    def from_env(cls) -> "Settings":
        openai_key = os.getenv("OPENAI_API_KEY")
        sarvam_key = os.getenv("SARVAM_API_KEY")
        trvios_key = os.getenv("TRVIOS_API_KEY")
        return cls(
            app_env=os.getenv("APP_ENV", "development"),
            app_debug=os.getenv("APP_DEBUG", "false").lower() == "true",
            database_url=os.getenv("DATABASE_URL", "sqlite:///./app.db"),
            chroma_persist_dir=os.getenv("CHROMA_PERSIST_DIR", "./data/chroma"),
            openai_api_key=openai_key if openai_key else None,
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            api_host=os.getenv("API_HOST", "0.0.0.0"),
            api_port=int(os.getenv("API_PORT", "8000")),
            auto_index_trips=os.getenv("AUTO_INDEX_TRIPS", "true").lower() == "true",
            trvios_trips_api_url=os.getenv(
                "TRVIOS_TRIPS_API_URL",
                "https://api.trvios.com/api/ai/trips",
            ),
            trip_source=os.getenv("TRIP_SOURCE", "trvios").lower(),
            sarvam_api_key=sarvam_key if sarvam_key else None,
            trvios_api_key=trvios_key if trvios_key else None,
            google_places_api_key=os.getenv("GOOGLE_PLACES_API_KEY", "AIzaSyCcJn4CxZmLGoNXB2G10XV2N4K_gqRK6ww"),
            mongodb_uri=os.getenv("MONGODB_URI", "mongodb://localhost:27017"),
            mongodb_db_name=os.getenv("MONGODB_DB_NAME", "trip_chat"),
            spam_limit=int(os.getenv("SPAM_LIMIT", "10")),
            block_duration_hours=int(os.getenv("BLOCK_DURATION_HOURS", "48")),
            rate_limit_requests=int(os.getenv("RATE_LIMIT_REQUESTS", "30")),
            rate_limit_window_seconds=int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60")),
            ollama_model=os.getenv("OLLAMA_MODEL", "llama3.2"),

        )

    def ensure_directories(self) -> None:
        """Create required data directories."""
        Path(self.chroma_persist_dir).mkdir(parents=True, exist_ok=True)
