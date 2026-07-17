import uuid
from dataclasses import dataclass

from clean_app.domain.entities.knowledge import KnowledgeDocument
from clean_app.domain.repositories.vector_store import VectorStore
from clean_app.infrastructure.extraction.image_extractor import ImageExtractor
from clean_app.infrastructure.extraction.pdf_extractor import PdfExtractor
from clean_app.infrastructure.extraction.web_extractor import WebExtractor


@dataclass(frozen=True, slots=True)
class IngestResponse:
    id: str
    title: str
    url: str
    char_count: int
    total_in_store: int


class IngestWebsiteUseCase:
    """Orchestrates single web page download, text extraction, and indexing."""

    def __init__(self, web_extractor: WebExtractor, vector_store: VectorStore) -> None:
        self._web_extractor = web_extractor
        self._vector_store = vector_store

    async def execute(self, url: str) -> IngestResponse:
        cleaned_text, title = await self._web_extractor.extract_text_and_title(url)
        # Generate stable UUID for website based on URL namespace
        doc_id = str(uuid.uuid5(uuid.NAMESPACE_URL, url))

        doc = KnowledgeDocument(
            id=doc_id,
            title=title,
            url=url,
            content=cleaned_text,
        )
        self._vector_store.add_knowledge_documents([doc])
        return IngestResponse(
            id=doc.id,
            title=doc.title,
            url=doc.url,
            char_count=len(doc.content),
            total_in_store=self._vector_store.count_knowledge(),
        )


class IngestPdfUseCase:
    """Orchestrates PDF text extraction and indexing."""

    def __init__(self, pdf_extractor: PdfExtractor, vector_store: VectorStore) -> None:
        self._pdf_extractor = pdf_extractor
        self._vector_store = vector_store

    def execute(self, filename: str, pdf_bytes: bytes) -> IngestResponse:
        extracted_text = self._pdf_extractor.extract_text(pdf_bytes)
        # Create a unique identifier for PDF
        random_suffix = str(uuid.uuid4())[:8]
        doc_id = f"pdf_{random_suffix}_{filename}"
        url = f"file:///uploaded_pdfs/{filename}"

        doc = KnowledgeDocument(
            id=doc_id,
            title=filename,
            url=url,
            content=extracted_text,
        )
        self._vector_store.add_knowledge_documents([doc])
        return IngestResponse(
            id=doc.id,
            title=doc.title,
            url=doc.url,
            char_count=len(doc.content),
            total_in_store=self._vector_store.count_knowledge(),
        )


class IngestImageUseCase:
    """Orchestrates vision-based image text extraction and indexing."""

    def __init__(self, image_extractor: ImageExtractor, vector_store: VectorStore) -> None:
        self._image_extractor = image_extractor
        self._vector_store = vector_store

    async def execute(self, filename: str, image_bytes: bytes, mime_type: str) -> IngestResponse:
        extracted_text = await self._image_extractor.extract_text(image_bytes, mime_type)
        # Create a unique identifier for image
        random_suffix = str(uuid.uuid4())[:8]
        doc_id = f"img_{random_suffix}_{filename}"
        url = f"file:///uploaded_images/{filename}"

        doc = KnowledgeDocument(
            id=doc_id,
            title=filename,
            url=url,
            content=extracted_text,
        )
        self._vector_store.add_knowledge_documents([doc])
        return IngestResponse(
            id=doc.id,
            title=doc.title,
            url=doc.url,
            char_count=len(doc.content),
            total_in_store=self._vector_store.count_knowledge(),
        )
