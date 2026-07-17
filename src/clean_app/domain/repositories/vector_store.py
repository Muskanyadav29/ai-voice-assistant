"""Vector store repository interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from clean_app.domain.entities.trip import Trip
from clean_app.domain.entities.knowledge import KnowledgeDocument


@dataclass(frozen=True, slots=True)
class TripSearchResult:
    """A trip matched by semantic search."""

    trip: Trip
    score: float


@dataclass(frozen=True, slots=True)
class KnowledgeSearchResult:
    """A knowledge document matched by semantic search."""

    document: KnowledgeDocument
    score: float


class VectorStore(ABC):
    """Port for indexing and searching trip and platform knowledge embeddings."""

    @abstractmethod
    def index_trips(self, trips: list[Trip]) -> int:
        """Embed and store trips. Returns number of indexed records."""

    @abstractmethod
    def search(self, query: str, top_k: int = 3) -> list[TripSearchResult]:
        """Find trips most relevant to the user query."""

    @abstractmethod
    def count(self) -> int:
        """Return how many trips are currently indexed."""

    @abstractmethod
    def index_knowledge(self, documents: list[KnowledgeDocument]) -> int:
        """Embed and store platform knowledge documents. Returns number of indexed records."""

    @abstractmethod
    def search_knowledge(self, query: str, top_k: int = 3) -> list[KnowledgeSearchResult]:
        """Find platform knowledge documents most relevant to the user query."""

    @abstractmethod
    def count_knowledge(self) -> int:
        """Return how many platform knowledge documents are currently indexed."""

    @abstractmethod
    def add_knowledge_documents(self, documents: list[KnowledgeDocument]) -> int:
        """Add platform knowledge documents without removing any existing ones. Returns count of newly added documents."""

