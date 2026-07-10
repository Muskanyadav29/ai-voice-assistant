"""KnowledgeDocument domain entity."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class KnowledgeDocument:
    """Represents a single website page or section for general platform knowledge."""

    id: str
    title: str
    url: str
    content: str

    def to_search_text(self) -> str:
        """Build text representation for vector indexing."""
        return f"Page URL: {self.url}\nTitle: {self.title}\nContent: {self.content}"
