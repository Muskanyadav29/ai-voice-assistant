"""Run the FastAPI server."""

import uvicorn

from clean_app.infrastructure.config.settings import Settings


def run_api() -> None:
    """Start the trip chat API."""
    settings = Settings.from_env()

    uvicorn.run(
        "clean_app.presentation.api.app:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.app_debug,
    )