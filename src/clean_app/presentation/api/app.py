"""FastAPI application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from clean_app.presentation.api.dependencies import AppContainer, build_container
from clean_app.presentation.api.routes import chat, trips, bookings, places

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize services and optionally index trips and platform knowledge on startup."""
    container: AppContainer = app.state.container
    if container.settings.auto_index_trips:
        container.index_trips.execute()
        container.index_knowledge.execute()
    yield


def create_app(container: AppContainer | None = None) -> FastAPI:
    """Build the FastAPI application."""
    resolved_container = container or build_container()

    app = FastAPI(
        title="Trip Chat API",
        description="AI streaming chat over trip data with vector search (RAG).",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.container = resolved_container

    @app.get("/health")
    def health() -> dict[str, str | int]:
        return {
            "status": "ok",
            "indexed_trips": resolved_container.vector_store.count(),
        }

    app.include_router(trips.router, prefix="/api")
    app.include_router(chat.router, prefix="/api")
    app.include_router(bookings.router, prefix="/api")
    app.include_router(places.router, prefix="/api")

    if WEB_DIR.is_dir():
        app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")

    return app
app = create_app()
