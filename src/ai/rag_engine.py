from __future__ import annotations

from dataclasses import dataclass

from src.ai.document_indexer import DocumentIndexer, DocumentIndexResult
from src.ai.local_llm import LocalLLM
from src.ai.model_manager import ModelManager
from src.ai.vector_index import SearchResult


@dataclass(frozen=True)
class RAGReadiness:
    ready: bool
    missing: tuple[str, ...]
    message: str


class RAGEngine:
    """Readiness gate for local source-grounded PDF chat."""

    def __init__(self, manager: ModelManager | None = None):
        self.manager = manager or ModelManager()
        self.llm = LocalLLM(self.manager)
        self.indexer = DocumentIndexer()

    def readiness(self) -> RAGReadiness:
        required = ("local_llm", "embedding_model")
        missing = []
        for model_id in required:
            status = self.manager.status(model_id)
            if not status.installed:
                missing.append(status.spec.name)

        if missing:
            return RAGReadiness(
                False,
                tuple(missing),
                "Yerel RAG için eksik modeller var: " + ", ".join(missing),
            )

        return RAGReadiness(True, (), "Yerel RAG altyapısı için gerekli modeller hazır.")

    def index_document(
        self,
        pdf_path: str,
        *,
        force_rebuild: bool = False,
        use_ocr: bool = True,
    ) -> DocumentIndexResult:
        return self.indexer.load_or_build(pdf_path, force_rebuild=force_rebuild, use_ocr=use_ocr)

    def search_document(
        self,
        pdf_path: str,
        query: str,
        *,
        top_k: int = 5,
        force_rebuild: bool = False,
        use_ocr: bool = True,
    ) -> list[SearchResult]:
        result = self.index_document(pdf_path, force_rebuild=force_rebuild, use_ocr=use_ocr)
        return self.indexer.search(result.index, query, top_k=top_k)
