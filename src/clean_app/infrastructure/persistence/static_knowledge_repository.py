"""Static platform knowledge repository implementation."""

from clean_app.domain.entities.knowledge import KnowledgeDocument
from clean_app.domain.repositories.knowledge_repository import KnowledgeRepository
from clean_app.infrastructure.persistence.platform_knowledge_data import PLATFORM_PAGES_DATA


class StaticKnowledgeRepository(KnowledgeRepository):
    """Loads platform-wide knowledge from pre-compiled static training page data."""

    def get_all(self) -> list[KnowledgeDocument]:
        return [
            KnowledgeDocument(
                id=item["id"],
                title=item["title"],
                url=item["url"],
                content=item["content"],
            )
            for item in PLATFORM_PAGES_DATA
        ]
