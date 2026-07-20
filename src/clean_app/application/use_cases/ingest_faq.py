"""Use case for training/indexing FAQ questions and answers into the vector store."""

import uuid
from dataclasses import dataclass
from typing import Sequence

from clean_app.domain.entities.knowledge import KnowledgeDocument
from clean_app.domain.repositories.vector_store import VectorStore


@dataclass(frozen=True, slots=True)
class FaqItem:
    question: str
    answer: str
    category: str = "General"


@dataclass(frozen=True, slots=True)
class IngestFaqResponse:
    added_count: int
    total_in_store: int
    sample_ids: list[str]


class IngestFaqUseCase:
    """Orchestrates FAQ training and indexing into the vector store."""

    def __init__(self, vector_store: VectorStore) -> None:
        self._vector_store = vector_store

    def execute(self, faqs: Sequence[FaqItem | dict[str, str]]) -> IngestFaqResponse:
        documents: list[KnowledgeDocument] = []
        sample_ids: list[str] = []

        for item in faqs:
            if isinstance(item, dict):
                q = item.get("question") or item.get("q") or ""
                a = item.get("answer") or item.get("a") or ""
                cat = item.get("category", "General")
            else:
                q = item.question
                a = item.answer
                cat = item.category

            if not q or not a:
                continue

            # Generate stable deterministic ID based on question text
            doc_id = f"faq_{uuid.uuid3(uuid.NAMESPACE_DNS, q.strip().lower())}"
            title = f"FAQ: {q.strip()}"
            url = f"https://trvios.com/faq#{doc_id}"
            content = f"Category: {cat}\nQuestion: {q.strip()}\nAnswer: {a.strip()}"

            doc = KnowledgeDocument(
                id=doc_id,
                title=title,
                url=url,
                content=content,
            )
            documents.append(doc)
            sample_ids.append(doc_id)

        if documents:
            self._vector_store.add_knowledge_documents(documents)

        return IngestFaqResponse(
            added_count=len(documents),
            total_in_store=self._vector_store.count_knowledge(),
            sample_ids=sample_ids,
        )
