from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from src.ai.document_loader import DocumentChunk, DocumentLoadResult, DocumentLoader, DocumentPage, TextBlock
from src.ai.embedding_engine import HashingEmbeddingEngine
from src.ai.ocr_engine import OCREngine
from src.ai.vector_index import SearchResult, SimpleVectorIndex, VectorRecord
from src.core.config_manager import cfg


INDEX_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class DocumentIndexMetadata:
    document_path: str
    cache_key: str
    file_size: int
    file_mtime_ns: int
    built_at: float
    page_count: int
    chunk_count: int
    used_ocr: bool
    embedding_engine: str
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class DocumentIndexResult:
    document: DocumentLoadResult
    index: SimpleVectorIndex
    metadata: DocumentIndexMetadata
    cache_path: str
    from_cache: bool = False


class DocumentIndexer:
    """Builds and caches local searchable PDF indexes."""

    def __init__(
        self,
        loader: DocumentLoader | None = None,
        embedding_engine: HashingEmbeddingEngine | None = None,
        ocr_engine: OCREngine | None = None,
        cache_dir: str | None = None,
    ):
        self.loader = loader or DocumentLoader()
        self.embedding_engine = embedding_engine or HashingEmbeddingEngine()
        self.ocr_engine = ocr_engine or OCREngine()
        self.cache_dir = Path(cache_dir).expanduser() if cache_dir else self._default_cache_dir()

    def load_or_build(
        self,
        pdf_path: str,
        *,
        force_rebuild: bool = False,
        use_ocr: bool = True,
    ) -> DocumentIndexResult:
        path = Path(pdf_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(pdf_path)

        self.cache_dir = self._ensure_cache_dir()
        cache_key = self.cache_key(path, use_ocr=use_ocr)
        cache_path = self.cache_dir / f"{cache_key}.json"

        if cache_path.exists() and not force_rebuild:
            try:
                return self._load_cache(cache_path, from_cache=True)
            except (OSError, ValueError, json.JSONDecodeError, KeyError, TypeError):
                pass

        document = self.loader.load_pdf(str(path), use_ocr=use_ocr, ocr_engine=self.ocr_engine)
        index = self._build_vector_index(cache_key, document)
        stat = path.stat()
        metadata = DocumentIndexMetadata(
            document_path=str(path),
            cache_key=cache_key,
            file_size=int(stat.st_size),
            file_mtime_ns=int(stat.st_mtime_ns),
            built_at=time.time(),
            page_count=len(document.pages),
            chunk_count=len(document.chunks),
            used_ocr=document.used_ocr,
            embedding_engine=self.embedding_engine.info.engine_id,
            warnings=document.warnings,
        )
        result = DocumentIndexResult(document, index, metadata, str(cache_path), from_cache=False)
        self._save_cache(result)
        return result

    def search(self, index: SimpleVectorIndex, query: str, top_k: int = 5) -> list[SearchResult]:
        return index.search(self.embedding_engine.embed_text(query), top_k=top_k)

    def cache_key(self, path: Path, *, use_ocr: bool) -> str:
        stat = path.stat()
        payload = {
            "schema": INDEX_SCHEMA_VERSION,
            "path": str(path.resolve()).casefold(),
            "size": int(stat.st_size),
            "mtime_ns": int(stat.st_mtime_ns),
            "chunk_chars": self.loader.chunk_chars,
            "overlap_chars": self.loader.overlap_chars,
            "ocr": bool(use_ocr),
            "ocr_dpi": self.loader.ocr_dpi,
            "embedding": self.embedding_engine.info.engine_id,
        }
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def _build_vector_index(self, cache_key: str, document: DocumentLoadResult) -> SimpleVectorIndex:
        index = SimpleVectorIndex(dimension=self.embedding_engine.info.dimension)
        for chunk in document.chunks:
            record = VectorRecord(
                id=f"{cache_key}:p{chunk.page_number}:c{chunk.chunk_index}",
                text=chunk.text,
                page_number=chunk.page_number,
                metadata={
                    "chunk_index": chunk.chunk_index,
                    "bbox": chunk.bbox,
                    "source": chunk.source,
                    "char_start": chunk.char_start,
                    "char_end": chunk.char_end,
                    "document_path": document.path,
                },
            )
            index.add(record, self.embedding_engine.embed_text(chunk.text))
        return index

    def _save_cache(self, result: DocumentIndexResult):
        target = Path(result.cache_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema": INDEX_SCHEMA_VERSION,
            "metadata": asdict(result.metadata),
            "document": self._document_to_dict(result.document),
            "index": result.index.to_dict(),
        }
        temp = target.with_suffix(target.suffix + ".tmp")
        temp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        temp.replace(target)

    def _load_cache(self, cache_path: Path, *, from_cache: bool) -> DocumentIndexResult:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        if int(payload.get("schema", 0)) != INDEX_SCHEMA_VERSION:
            raise ValueError("Unsupported cache schema.")

        metadata_payload = payload["metadata"]
        metadata = DocumentIndexMetadata(
            document_path=metadata_payload["document_path"],
            cache_key=metadata_payload["cache_key"],
            file_size=int(metadata_payload["file_size"]),
            file_mtime_ns=int(metadata_payload["file_mtime_ns"]),
            built_at=float(metadata_payload["built_at"]),
            page_count=int(metadata_payload["page_count"]),
            chunk_count=int(metadata_payload["chunk_count"]),
            used_ocr=bool(metadata_payload["used_ocr"]),
            embedding_engine=metadata_payload["embedding_engine"],
            warnings=tuple(metadata_payload.get("warnings", ())),
        )
        document = self._document_from_dict(payload["document"])
        index = SimpleVectorIndex.from_dict(payload["index"])
        return DocumentIndexResult(document, index, metadata, str(cache_path), from_cache=from_cache)

    def _document_to_dict(self, document: DocumentLoadResult) -> dict:
        return {
            "path": document.path,
            "warnings": list(document.warnings),
            "used_ocr": document.used_ocr,
            "pages": [
                {
                    "page_number": page.page_number,
                    "text": page.text,
                    "width": page.width,
                    "height": page.height,
                    "source": page.source,
                    "ocr_used": page.ocr_used,
                    "warnings": list(page.warnings),
                    "text_blocks": [asdict(block) for block in page.text_blocks],
                }
                for page in document.pages
            ],
            "chunks": [asdict(chunk) for chunk in document.chunks],
        }

    def _document_from_dict(self, payload: dict) -> DocumentLoadResult:
        pages = []
        for page_payload in payload.get("pages", []):
            blocks = tuple(
                TextBlock(
                    page_number=int(block["page_number"]),
                    text=block["text"],
                    bbox=tuple(block["bbox"]),
                    source=block.get("source", "text"),
                    confidence=block.get("confidence"),
                )
                for block in page_payload.get("text_blocks", [])
            )
            pages.append(
                DocumentPage(
                    page_number=int(page_payload["page_number"]),
                    text=page_payload.get("text", ""),
                    width=float(page_payload.get("width", 0.0)),
                    height=float(page_payload.get("height", 0.0)),
                    text_blocks=blocks,
                    source=page_payload.get("source", "text"),
                    ocr_used=bool(page_payload.get("ocr_used", False)),
                    warnings=tuple(page_payload.get("warnings", ())),
                )
            )

        chunks = tuple(
            DocumentChunk(
                page_number=int(chunk["page_number"]),
                text=chunk["text"],
                chunk_index=int(chunk["chunk_index"]),
                bbox=tuple(chunk["bbox"]) if chunk.get("bbox") else None,
                source=chunk.get("source", "text"),
                char_start=int(chunk.get("char_start", 0)),
                char_end=int(chunk.get("char_end", 0)),
            )
            for chunk in payload.get("chunks", [])
        )
        return DocumentLoadResult(
            path=payload["path"],
            pages=tuple(pages),
            chunks=chunks,
            warnings=tuple(payload.get("warnings", ())),
            used_ocr=bool(payload.get("used_ocr", False)),
        )

    def _ensure_cache_dir(self) -> Path:
        last_error = None
        for candidate in self._cache_dir_candidates():
            try:
                candidate.mkdir(parents=True, exist_ok=True)
                return candidate.resolve()
            except OSError as exc:
                last_error = exc
        if last_error:
            raise last_error
        return self.cache_dir

    def _cache_dir_candidates(self) -> list[Path]:
        candidates = [self.cache_dir]
        local_appdata = os.getenv("LOCALAPPDATA")
        if local_appdata:
            candidates.append(Path(local_appdata) / "PDFAura" / "ai_index_cache")
        candidates.append(Path.cwd() / ".cache" / "ai_index")
        candidates.append(Path(__file__).resolve().parents[2] / ".cache" / "ai_index")

        unique: list[Path] = []
        seen = set()
        for candidate in candidates:
            key = str(candidate)
            if key not in seen:
                seen.add(key)
                unique.append(candidate)
        return unique

    @staticmethod
    def _default_cache_dir() -> Path:
        return Path(cfg.config_dir).expanduser() / "ai_index_cache"
