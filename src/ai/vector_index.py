"""Local vector search for PDF Aura's RAG features.

The default embedding is a deterministic hashing bag-of-words: no model
download, no network, no extra dependency. It is good enough for locating the
page that talks about a word the user asked about. FAISS is used when it is
installed, otherwise NumPy does the cosine dot product, and a pure-Python loop
keeps the module importable when even NumPy is missing.
"""
from __future__ import annotations

import hashlib
import logging
import math
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable, Sequence

try:  # optional: much faster matrix search
    import numpy as np
except Exception:  # pragma: no cover - exercised only without numpy
    np = None

try:  # optional: only used when the user has faiss installed
    import faiss
except Exception:  # pragma: no cover - the normal install has no faiss
    faiss = None


logger = logging.getLogger(__name__)

DEFAULT_DIM = 1024
_WORD_RE = re.compile(r"[^\W_]+", re.UNICODE)


def _normalize_token(token: str) -> str:
    token = unicodedata.normalize("NFKC", token).casefold()
    # "İ".casefold() leaves a combining dot; it must not become a new word.
    return "".join(char for char in token if not unicodedata.combining(char))


def tokenize(text: str) -> list[str]:
    """Lowercase words, with Turkish dotted/dotless I folded together."""
    return [_normalize_token(token)
            for token in _WORD_RE.findall(str(text or ""))]


@lru_cache(maxsize=32768)
def _bucket(token: str, dim: int) -> int:
    digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big") % dim


class HashingEmbedder:
    """Stateless hashing embedding with sublinear term frequency."""

    def __init__(self, dim: int = DEFAULT_DIM):
        if int(dim) < 16:
            raise ValueError("Embedding boyutu en az 16 olmalı.")
        self.dim = int(dim)

    def embed(self, text: str) -> list[float]:
        counts: dict[int, int] = {}
        for token in tokenize(text):
            bucket = _bucket(token, self.dim)
            counts[bucket] = counts.get(bucket, 0) + 1

        vector = [0.0] * self.dim
        for bucket, count in counts.items():
            vector[bucket] = 1.0 + math.log(count)

        norm = math.sqrt(sum(value * value for value in vector))
        if norm:
            vector = [value / norm for value in vector]
        return vector

    def embed_many(self, texts: Iterable[str]) -> list[list[float]]:
        return [self.embed(text) for text in texts]


def embed_text(text: str, dim: int = DEFAULT_DIM) -> list[float]:
    """Convenience wrapper for callers that only need one vector."""
    return HashingEmbedder(dim=dim).embed(text)


@dataclass(frozen=True)
class SearchHit:
    chunk: object
    score: float

    @property
    def page_number(self) -> int:
        if isinstance(self.chunk, dict):
            return int(self.chunk.get("page_number", 0) or 0)
        return int(getattr(self.chunk, "page_number", 0) or 0)

    @property
    def text(self) -> str:
        if isinstance(self.chunk, dict):
            return str(self.chunk.get("text", ""))
        return str(getattr(self.chunk, "text", ""))

    @property
    def chunk_id(self) -> str:
        if isinstance(self.chunk, dict):
            return str(self.chunk.get("chunk_id", ""))
        return str(getattr(self.chunk, "chunk_id", ""))


def _chunk_text(chunk) -> str:
    if isinstance(chunk, dict):
        return str(chunk.get("text", ""))
    return str(getattr(chunk, "text", ""))


class VectorIndex:
    """A local cosine index over document chunks."""

    def __init__(self, chunks: Sequence[object] | None = None,
                 embedder: HashingEmbedder | None = None,
                 backend: str = "auto"):
        self.chunks = list(chunks or ())
        self.embedder = embedder or HashingEmbedder()
        self.requested_backend = backend
        self.backend = "empty"
        self._matrix = None
        self._vectors: list[list[float]] = []
        self._faiss_index = None
        self.build()

    @classmethod
    def from_document(cls, document, embedder: HashingEmbedder | None = None,
                      backend: str = "auto") -> "VectorIndex":
        return cls(getattr(document, "chunks", ()), embedder=embedder,
                   backend=backend)

    def build(self) -> None:
        self._matrix = None
        self._vectors = []
        self._faiss_index = None

        if not self.chunks:
            self.backend = "empty"
            return

        texts = [_chunk_text(chunk) for chunk in self.chunks]
        if np is not None:
            self._matrix = np.asarray(self.embedder.embed_many(texts),
                                      dtype="float32")
        else:  # pragma: no cover - numpy ships with the app
            self._vectors = self.embedder.embed_many(texts)

        if (self.requested_backend in ("auto", "faiss") and faiss is not None
                and self._matrix is not None):
            try:
                index = faiss.IndexFlatIP(self.embedder.dim)
                index.add(self._matrix)
                self._faiss_index = index
                self.backend = "faiss"
                return
            except Exception as exc:
                logger.warning("FAISS index could not be built: %s", exc)

        self.backend = "numpy" if self._matrix is not None else "python"

    def _query_vector(self, question: str):
        if np is not None:
            return np.asarray(self.embedder.embed(question), dtype="float32")
        return self.embedder.embed(question)  # pragma: no cover

    def search(self, question: str, top_k: int = 5,
               min_score: float = 0.0) -> list[SearchHit]:
        """Return the closest chunks, best first, above *min_score*."""
        if not self.chunks or not str(question or "").strip():
            return []

        try:
            top_k = max(1, int(top_k))
        except (TypeError, ValueError):
            top_k = 5
        top_k = min(top_k, len(self.chunks))

        query = self._query_vector(question)
        if not any(float(value) for value in query):
            return []

        pairs: list[tuple[int, float]] = []
        if self._faiss_index is not None:
            scores, indices = self._faiss_index.search(
                query.reshape(1, -1), top_k)
            pairs = [(int(index), float(score))
                     for index, score in zip(indices[0], scores[0])
                     if int(index) >= 0]
        elif self._matrix is not None:
            scores = self._matrix @ query
            order = np.argsort(-scores)[:top_k]
            pairs = [(int(index), float(scores[index])) for index in order]
        else:  # pragma: no cover - numpy ships with the app
            for index, vector in enumerate(self._vectors):
                pairs.append((index, sum(a * b for a, b in zip(vector, query))))
            pairs.sort(key=lambda item: item[1], reverse=True)
            pairs = pairs[:top_k]

        hits = []
        for index, score in pairs:
            if score > float(min_score):
                hits.append(SearchHit(chunk=self.chunks[index], score=round(score, 6)))
        return hits


def build_index(chunks: Sequence[object], *, embedder: HashingEmbedder | None = None,
                backend: str = "auto") -> VectorIndex:
    return VectorIndex(chunks, embedder=embedder, backend=backend)
