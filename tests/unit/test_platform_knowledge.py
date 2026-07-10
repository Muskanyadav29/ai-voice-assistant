"""Unit tests for platform knowledge indexing and searching in ChromaDB."""

from clean_app.domain.entities.knowledge import KnowledgeDocument
from clean_app.infrastructure.vector.chroma_vector_store import ChromaVectorStore


def test_chroma_knowledge_indexing_and_search(tmp_path) -> None:
    # 1. Initialize store using temp path
    store = ChromaVectorStore(str(tmp_path))
    assert store.count_knowledge() == 0

    # 2. Construct mock platform documents
    docs = [
        KnowledgeDocument(
            id="page_split",
            title="Split Bills Tool",
            url="https://trvios.com/split-bills",
            content="Calculate shares and automatically split group travel expenses.",
        ),
        KnowledgeDocument(
            id="page_partner",
            title="Become a Partner",
            url="https://trvios.com/become-partner",
            content="Tour operators and hosts can publish packages and track earnings.",
        ),
    ]

    # 3. Index documents
    added = store.index_knowledge(docs)
    assert added == 2
    assert store.count_knowledge() == 2

    # Indexing same docs should count as 0 newly added
    added_re = store.index_knowledge(docs)
    assert added_re == 0

    # 4. Perform vector search
    results = store.search_knowledge("split travel bills", top_k=1)
    assert len(results) == 1
    assert results[0].document.id == "page_split"
    assert results[0].document.title == "Split Bills Tool"
    assert results[0].score > 0.0
