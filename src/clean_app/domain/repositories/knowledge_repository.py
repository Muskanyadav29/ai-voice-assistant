"""KnowledgeRepository interface."""

from abc import ABC, abstractmethod

from clean_app.domain.entities.knowledge import KnowledgeDocument


class KnowledgeRepository(ABC):
    """Port for retrieving platform-wide knowledge documents."""

    @abstractmethod
    def get_all(self) -> list[KnowledgeDocument]:
        """Fetch all platform knowledge documents."""
