"""Index platform knowledge into the vector store."""

from dataclasses import dataclass
from clean_app.domain.repositories.knowledge_repository import KnowledgeRepository
from clean_app.domain.repositories.vector_store import VectorStore


@dataclass(frozen=True, slots=True)
class IndexKnowledgeResponse:
    """Output after indexing knowledge into the vector store."""

    indexed_count: int
    total_in_store: int


class IndexKnowledgeUseCase:
    """Load platform website pages and embed them for semantic search."""

    def __init__(
        self,
        knowledge_repository: KnowledgeRepository,
        vector_store: VectorStore,
    ) -> None:
        self._knowledge_repository = knowledge_repository
        self._vector_store = vector_store

    def execute(self) -> IndexKnowledgeResponse:
        documents = self._knowledge_repository.get_all()
        indexed_count = self._vector_store.index_knowledge(documents)
        return IndexKnowledgeResponse(
            indexed_count=indexed_count,
            total_in_store=self._vector_store.count_knowledge(),
        )
