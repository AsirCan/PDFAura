from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass

import numpy as np


TOKEN_RE = re.compile(r"\w+", re.UNICODE)


@dataclass(frozen=True)
class EmbeddingInfo:
    engine_id: str
    dimension: int
    description: str


class HashingEmbeddingEngine:
    """Fast deterministic local embedding fallback.

    This is not a neural semantic model. It gives Phase 2 a reliable offline
    vector representation for search/cache/index plumbing until the heavier
    embedding model is wired into the Phase 3 RAG runtime.
    """

    def __init__(self, dimension: int = 512):
        self.dimension = max(128, int(dimension))
        self.info = EmbeddingInfo(
            engine_id=f"hashing-lexical-v1-{self.dimension}",
            dimension=self.dimension,
            description="Local lexical hashing embedding fallback",
        )

    def embed_text(self, text: str) -> np.ndarray:
        vector = np.zeros(self.dimension, dtype=np.float32)
        normalized = self._normalize(text)
        if not normalized:
            return vector

        tokens = TOKEN_RE.findall(normalized)
        for token in tokens:
            self._add_feature(vector, f"tok:{token}", 1.0)

        for left, right in zip(tokens, tokens[1:]):
            self._add_feature(vector, f"bi:{left}_{right}", 1.2)

        compact = "".join(tokens)
        for index in range(max(0, len(compact) - 2)):
            self._add_feature(vector, f"tri:{compact[index:index + 3]}", 0.25)

        norm = float(np.linalg.norm(vector))
        if norm > 0:
            vector /= norm
        return vector

    def embed_many(self, texts: list[str] | tuple[str, ...]) -> list[np.ndarray]:
        return [self.embed_text(text) for text in texts]

    def _add_feature(self, vector: np.ndarray, feature: str, weight: float):
        digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
        value = int.from_bytes(digest, "little", signed=False)
        position = value % self.dimension
        sign = 1.0 if ((value >> 63) & 1) == 0 else -1.0
        vector[position] += np.float32(sign * weight)

    @staticmethod
    def _normalize(text: str) -> str:
        normalized = unicodedata.normalize("NFKC", text or "")
        return normalized.casefold()
