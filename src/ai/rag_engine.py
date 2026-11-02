"""Source-grounded local RAG over a single PDF.

``RagEngine.ask(pdf, question)`` loads (or reuses the cached) document, finds
the most relevant chunks with the local hashing index, and asks the local LLM
to answer *only* from those chunks. The answer carries the page number and a
short quote for every source used. When no local LLM is installed, the best
chunk is returned as an extractive answer instead.

If nothing relevant is found the engine says so instead of making something
up. Both the loading and the generation stages accept a progress callback and
a cancel callback (a callable or a ``TaskContext``).
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from src.ai.document_loader import (
    LoadedDocument,
    check_cancelled,
    load_document,
    report_progress,
)
from src.ai.local_llm import LocalLLM
from src.ai.vector_index import HashingEmbedder, SearchHit, VectorIndex, tokenize
from src.core.config_manager import cfg
from src.core.task_manager import CancelledError


logger = logging.getLogger(__name__)

ProgressCallback = Callable[..., None]
CancelCheck = Callable[[], bool] | None

# Words that carry no meaning for "is this chunk about the question?".
_STOPWORDS = {
    "acaba", "ama", "ancak", "bir", "bu", "da", "daha", "de", "değil", "diye",
    "en", "gibi", "hem", "her", "hangi", "hakkında", "için", "ile", "ise",
    "kadar", "ki", "mi", "mu", "nasıl", "ne", "neden", "nerede", "niçin",
    "olan", "olarak", "olduğu", "şey", "ve", "veya", "ya", "yani",
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "do", "does",
    "for", "from", "how", "in", "is", "it", "of", "on", "or", "that", "the",
    "this", "to", "was", "were", "what", "when", "where", "which", "who",
    "why", "with",
}

_MESSAGES = {
    "tr": {
        "not_found": "Bu bilgiyi belgede bulamadım.",
        "empty_question": "Lütfen bir soru yazın.",
        "empty_document": "Bu belgede aranabilir metin bulunamadı.",
    },
    "en": {
        "not_found": "I could not find this in the document.",
        "empty_question": "Please type a question.",
        "empty_document": "No searchable text was found in this document.",
    },
}

_REFUSAL_MARKERS = (
    "bulamadım", "bulunamadı", "bulunmuyor", "belgede yok", "kaynakta yok",
    "could not find", "cannot find", "can't find", "not found",
    "not mentioned", "no information", "does not mention", "not in the document",
)

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?…])\s+|\n+")


def _message(key: str) -> str:
    language = str(cfg.get("language", "tr")).lower()[:2]
    table = _MESSAGES.get(language, _MESSAGES["en"])
    return table.get(key, _MESSAGES["tr"][key])


def _question_tokens(question: str) -> set[str]:
    return {token for token in tokenize(question) if token not in _STOPWORDS}


def _relevant(question: str, hit: SearchHit, *, strong_score: float = 0.35) -> bool:
    """Guard against hash collisions: a shared word, or a very high score."""
    tokens = _question_tokens(question)
    if not tokens:
        return False
    if tokens & set(tokenize(hit.text)):
        return True
    return hit.score >= strong_score


def _collapse(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _quote(text: str, question: str, max_chars: int = 240) -> str:
    """A short passage around the first query word, for the source list."""
    collapsed = _collapse(text)
    if len(collapsed) <= max_chars:
        return collapsed

    lowered = collapsed.casefold()
    position = -1
    for token in tokenize(question):
        if token in _STOPWORDS:
            continue
        position = lowered.find(token)
        if position >= 0:
            break
    if position < 0:
        position = 0

    start = max(0, position - 60)
    end = min(len(collapsed), start + max_chars)
    start = collapsed.rfind(" ", 0, start) if start > 0 else 0
    if end < len(collapsed):
        cut = collapsed.rfind(" ", start, end)
        if cut > start:
            end = cut
    snippet = collapsed[start:end].strip()
    if start > 0:
        snippet = "…" + snippet
    if end < len(collapsed):
        snippet += "…"
    return snippet


def _best_sentences(text: str, question: str, max_chars: int = 600) -> str:
    """Extractive answer: the sentences sharing most words with the question."""
    sentences = [sentence.strip() for sentence in _SENTENCE_SPLIT.split(text or "")
                 if sentence.strip()]
    if not sentences:
        return _collapse(text)[:max_chars]

    tokens = _question_tokens(question)
    scored = []
    for index, sentence in enumerate(sentences):
        overlap = len(tokens & set(tokenize(sentence)))
        scored.append((overlap, index, sentence))

    chosen = [item for item in sorted(scored, key=lambda item: (-item[0], item[1]))
              if item[0] > 0][:2]
    if not chosen:
        return _collapse(sentences[0])[:max_chars]

    chosen.sort(key=lambda item: item[1])
    answer = " ".join(item[2] for item in chosen)
    return _collapse(answer)[:max_chars]


@dataclass
class RagSource:
    page_number: int
    quote: str
    score: float = 0.0
    chunk_id: str = ""


@dataclass
class RagAnswer:
    answer: str
    sources: list[RagSource] = field(default_factory=list)
    found: bool = True
    used_llm: bool = False
    document: LoadedDocument | None = None

    def to_dict(self) -> dict:
        return {
            "answer": self.answer,
            "found": self.found,
            "used_llm": self.used_llm,
            "sources": [
                {"page": source.page_number, "quote": source.quote,
                 "score": source.score, "chunk_id": source.chunk_id}
                for source in self.sources
            ],
        }


class RagEngine:
    """Ask questions about one or more PDFs, locally and with sources."""

    def __init__(self, llm: LocalLLM | None = None, *, use_llm: bool = True,
                 embedder: HashingEmbedder | None = None, top_k: int = 4,
                 min_score: float = 0.05,
                 cache_dir: str | Path | None = None):
        if llm is not None:
            self.llm = llm
        elif use_llm:
            self.llm = LocalLLM()
        else:
            self.llm = None
        self.embedder = embedder or HashingEmbedder()
        self.top_k = max(1, int(top_k))
        self.min_score = float(min_score)
        self.cache_dir = cache_dir
        self._indices: dict[str, tuple[str, VectorIndex]] = {}

    def _index_for(self, document: LoadedDocument) -> VectorIndex:
        cached = self._indices.get(document.path)
        if cached and cached[0] == document.file_hash:
            return cached[1]
        index = VectorIndex(document.chunks, embedder=self.embedder)
        self._indices[document.path] = (document.file_hash, index)
        return index

    def _prompt(self, question: str, hits: list[SearchHit]) -> str:
        parts = [
            "Sen yerel bir belge asistanısın. Yalnızca aşağıdaki kaynak "
            "parçalarını kullanarak soruyu yanıtla. Kaynaklarda cevap yoksa "
            "sadece \"Belgede bulamadım.\" yaz. Bilgi uydurma.",
            "",
        ]
        budget = 5000
        for number, hit in enumerate(hits, start=1):
            text = _collapse(hit.text)
            block = f"[Kaynak {number} - Sayfa {hit.page_number}]\n{text}"
            if budget - len(block) < 0:
                block = block[:max(0, budget)]
            parts.append(block)
            parts.append("")
            budget -= len(block)
            if budget <= 0:
                break
        parts.append(f"Soru: {question.strip()}")
        parts.append("Cevap:")
        return "\n".join(parts)

    def _extractive(self, question: str, hits: list[SearchHit]) -> str:
        sections = []
        best_score = hits[0].score if hits else 0.0
        for hit in hits[:2]:
            if sections and hit.score < best_score * 0.5:
                break
            snippet = _best_sentences(hit.text, question)
            if snippet and snippet not in sections:
                sections.append(snippet)
            if sum(len(section) for section in sections) >= 600:
                break
        if sections:
            return "\n\n".join(sections)
        return _collapse(hits[0].text)[:600] if hits else ""

    def ask(self, pdf: str | Path, question: str, *,
            top_k: int | None = None, min_score: float | None = None,
            progress: ProgressCallback | None = None,
            cancel: CancelCheck = None) -> RagAnswer:
        """Answer *question* from *pdf*, with page-numbered sources."""
        question = str(question or "").strip()
        if not question:
            return RagAnswer(_message("empty_question"), [], found=False)

        check_cancelled(cancel)

        def load_progress(current, total, message=""):
            fraction = (current / total) if total else 0.0
            report_progress(progress, int(fraction * 40), 100, message)

        document = load_document(
            pdf, cache_dir=self.cache_dir, progress=load_progress, cancel=cancel)
        check_cancelled(cancel)

        if not document.chunks:
            return RagAnswer(_message("empty_document"), [], found=False,
                             document=document)

        report_progress(progress, 45, 100, "Ilgili sayfalar araniyor")
        index = self._index_for(document)
        limit = self.top_k if top_k is None else max(1, int(top_k))
        threshold = self.min_score if min_score is None else float(min_score)
        hits = [hit for hit in index.search(question, top_k=limit,
                                            min_score=threshold)
                if _relevant(question, hit)]
        check_cancelled(cancel)

        if not hits:
            report_progress(progress, 100, 100, "Kaynak bulunamadi")
            return RagAnswer(_message("not_found"), [], found=False,
                             document=document)

        sources = []
        seen = set()
        for hit in hits:
            source = RagSource(page_number=hit.page_number,
                               quote=_quote(hit.text, question),
                               score=hit.score, chunk_id=hit.chunk_id)
            key = (source.page_number, source.quote)
            if key not in seen:
                seen.add(key)
                sources.append(source)

        llm_ready = self.llm is not None and getattr(self.llm, "available", True)
        if llm_ready:
            report_progress(progress, 55, 100, "Cevap uretiliyor")

            def llm_progress(current, total, message=""):
                fraction = (current / total) if total else 0.0
                report_progress(progress, 55 + int(fraction * 40), 100, message)

            try:
                text = self.llm.generate(
                    self._prompt(question, hits), max_tokens=512,
                    temperature=0.1, progress=llm_progress, cancel=cancel)
            except CancelledError:
                raise
            except Exception as exc:
                # A broken runtime must not break the question; use the
                # extractive fallback below instead.
                logger.warning("Yerel LLM cevabı alınamadı: %s", exc)
                text = None
            if text:
                if any(marker in str(text).casefold()
                       for marker in _REFUSAL_MARKERS):
                    report_progress(progress, 100, 100, "Kaynak bulunamadi")
                    return RagAnswer(_message("not_found"), [], found=False,
                                     used_llm=True, document=document)
                report_progress(progress, 100, 100, "Cevap hazir")
                return RagAnswer(text, sources, found=True, used_llm=True,
                                 document=document)

        report_progress(progress, 100, 100, "Cevap hazir")
        return RagAnswer(self._extractive(question, hits), sources,
                         found=True, used_llm=False, document=document)


def ask(pdf: str | Path, question: str, **kwargs) -> RagAnswer:
    """Convenience wrapper around :class:`RagEngine`."""
    return RagEngine(**{key: value for key, value in kwargs.items()
                        if key in {"llm", "use_llm", "embedder", "top_k",
                                   "min_score", "cache_dir"}}).ask(
        pdf, question,
        **{key: value for key, value in kwargs.items()
           if key in {"top_k", "min_score", "progress", "cancel"}})
