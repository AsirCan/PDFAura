from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class VectorRecord:
    id: str
    text: str
    page_number: int
    metadata: dict


@dataclass(frozen=True)
class SearchResult:
    record: VectorRecord
    score: float


class SimpleVectorIndex:
    """Minimal local cosine-search index for the upcoming RAG layer."""

    def __init__(self, dimension: int | None = None):
        self.records: list[VectorRecord] = []
        self.vectors: np.ndarray | None = None
        self.dimension = dimension

    def add(self, record: VectorRecord, vector: np.ndarray):
        vector = np.asarray(vector, dtype=np.float32)
        if vector.ndim != 1:
            raise ValueError("Vector must be one-dimensional.")
        if self.dimension is None:
            self.dimension = int(vector.shape[0])
        elif self.dimension != int(vector.shape[0]):
            raise ValueError("Vector dimension mismatch.")

        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm

        self.records.append(record)
        if self.vectors is None:
            self.vectors = vector.reshape(1, -1)
            return

        if self.vectors.shape[1] != vector.shape[0]:
            raise ValueError("Vector dimension mismatch.")
        self.vectors = np.vstack([self.vectors, vector.reshape(1, -1)])

    def search(self, query_vector: np.ndarray, top_k: int = 5) -> list[SearchResult]:
        if self.vectors is None or not self.records:
            return []

        query = np.asarray(query_vector, dtype=np.float32)
        if query.ndim != 1:
            raise ValueError("Query vector must be one-dimensional.")
        if self.dimension is not None and query.shape[0] != self.dimension:
            raise ValueError("Query vector dimension mismatch.")

        norm = np.linalg.norm(query)
        if norm > 0:
            query = query / norm

        scores = self.vectors @ query
        top_indices = np.argsort(scores)[::-1][:max(1, top_k)]
        return [SearchResult(self.records[int(i)], float(scores[int(i)])) for i in top_indices]

    @property
    def count(self) -> int:
        return len(self.records)

    def save(self, path: str):
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.to_dict(), ensure_ascii=False), encoding="utf-8")

    def to_dict(self) -> dict:
        payload = {
            "schema": 2,
            "dimension": self.dimension,
            "records": [
                {
                    "id": r.id,
                    "text": r.text,
                    "page_number": r.page_number,
                    "metadata": r.metadata,
                }
                for r in self.records
            ],
            "vectors": self.vectors.tolist() if self.vectors is not None else [],
        }
        return payload

    @classmethod
    def load(cls, path: str) -> "SimpleVectorIndex":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(payload)

    @classmethod
    def from_dict(cls, payload: dict) -> "SimpleVectorIndex":
        index = cls()
        index.records = [
            VectorRecord(
                id=item["id"],
                text=item["text"],
                page_number=int(item["page_number"]),
                metadata=item.get("metadata", {}),
            )
            for item in payload.get("records", [])
        ]
        vectors = payload.get("vectors", [])
        index.vectors = np.asarray(vectors, dtype=np.float32) if vectors else None
        if payload.get("dimension"):
            index.dimension = int(payload["dimension"])
        elif index.vectors is not None:
            index.dimension = int(index.vectors.shape[1])
        return index
