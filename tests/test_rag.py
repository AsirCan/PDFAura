"""Faz 2/3: local document loading, vector search and source-grounded RAG."""
import math

import pytest

from src.ai import document_loader, local_llm, vector_index
from src.ai.document_loader import (
    DocumentChunk,
    PageText,
    TextBlock,
    chunk_page,
    load_document,
)
from src.ai.local_llm import LocalLLM, create_local_llm
from src.ai.rag_engine import RagEngine, ask
from src.ai.vector_index import HashingEmbedder, VectorIndex
from src.core.task_manager import CancelledError


def _text_pdf(path, pages):
    """A PDF whose pages contain real, extractable text."""
    import fitz

    document = fitz.open()
    try:
        for text in pages:
            page = document.new_page(width=595, height=842)
            page.insert_textbox(fitz.Rect(50, 50, 545, 800), text, fontsize=12)
        document.save(str(path))
    finally:
        document.close()
    return str(path)


@pytest.fixture
def faq_pdf(tmp_path):
    path = tmp_path / "sss.pdf"
    _text_pdf(path, [
        "The invoice total is 1200 TL. Payment is due on Friday.",
        "Cats sleep most of the day. A cat likes warm places.",
        "The support line is open between 09:00 and 17:00.",
    ])
    return path


# ── document_loader ────────────────────────────────────────────────────────

def test_loader_extracts_pages_blocks_and_chunks(faq_pdf, tmp_path):
    document = load_document(faq_pdf, cache_dir=tmp_path / "cache")

    assert [page.page_number for page in document.pages] == [1, 2, 3]
    assert "invoice total" in document.pages[0].text
    assert document.pages[0].blocks
    assert any(value > 0 for value in document.pages[0].blocks[0].bbox)
    assert document.chunks
    assert {chunk.page_number for chunk in document.chunks} <= {1, 2, 3}
    assert not document.from_cache


def test_second_load_comes_from_the_hash_cache(faq_pdf, tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    first = load_document(faq_pdf, cache_dir=cache)
    assert first.cache_path

    def fail(*args, **kwargs):
        raise AssertionError("cached PDF must not be read again")

    monkeypatch.setattr(document_loader, "extract_pages", fail)
    second = load_document(faq_pdf, cache_dir=cache)

    assert second.from_cache
    assert second.file_hash == first.file_hash
    assert [chunk.text for chunk in second.chunks] == [chunk.text for chunk in first.chunks]


def test_cache_is_invalidated_when_the_pdf_changes(tmp_path):
    path = tmp_path / "degisen.pdf"
    cache = tmp_path / "cache"
    _text_pdf(path, ["First version about apples."])
    load_document(path, cache_dir=cache)

    _text_pdf(path, ["Second version about oranges."])
    changed = load_document(path, cache_dir=cache)

    assert not changed.from_cache
    assert "oranges" in changed.pages[0].text


def test_corrupt_cache_is_rebuilt(tmp_path):
    path = tmp_path / "bozuk_cache.pdf"
    cache = tmp_path / "cache"
    _text_pdf(path, ["Recoverable text about pears."])
    first = load_document(path, cache_dir=cache)

    with open(first.cache_path, "w", encoding="utf-8") as handle:
        handle.write('{"version": 1, "pages": "not a list"}')

    rebuilt = load_document(path, cache_dir=cache)

    assert not rebuilt.from_cache
    assert "pears" in rebuilt.pages[0].text


def test_scanned_page_uses_the_ocr_fallback(tmp_path, monkeypatch):
    import fitz

    path = tmp_path / "taranmis.pdf"
    document = fitz.open()
    try:
        document.new_page(width=595, height=842)
        document.save(str(path))
    finally:
        document.close()

    monkeypatch.setattr(document_loader, "_ocr_page_text",
                        lambda page, lang=None, cancel=None: "Scanned invoice total 99 TL")
    loaded = load_document(path, cache_dir=tmp_path / "cache")

    assert loaded.pages[0].ocr_used
    assert "Scanned invoice" in loaded.pages[0].text


def test_ocr_failure_degrades_to_empty_page(tmp_path, monkeypatch):
    import fitz

    path = tmp_path / "bos.pdf"
    document = fitz.open()
    try:
        document.new_page(width=595, height=842)
        document.save(str(path))
    finally:
        document.close()

    monkeypatch.setattr(document_loader, "_ocr_page_text", lambda *args, **kwargs: "")
    loaded = load_document(path, cache_dir=tmp_path / "cache")

    assert loaded.pages[0].text == ""
    assert not loaded.pages[0].ocr_used
    assert loaded.chunks == ()


def test_long_page_is_split_into_overlapping_chunks():
    text = " ".join(f"word{index}" for index in range(200))
    page = PageText(page_number=7, text=text,
                    blocks=(TextBlock(text=text, bbox=(10, 20, 500, 700)),))

    chunks = chunk_page(page, chunk_size=200, chunk_overlap=40)

    assert len(chunks) >= 2
    assert all(chunk.page_number == 7 for chunk in chunks)
    assert all(len(chunk.text) <= 200 for chunk in chunks)
    assert chunks[1].start < chunks[0].end  # overlap
    assert all(chunk.bbox is not None for chunk in chunks)


def test_load_honours_cancel_and_reports_progress(faq_pdf, tmp_path):
    with pytest.raises(CancelledError):
        load_document(faq_pdf, cache_dir=tmp_path / "cache", cancel=lambda: True)

    seen = []
    load_document(faq_pdf, cache_dir=tmp_path / "cache", use_ocr=False,
                  progress=lambda current, total, message="": seen.append((current, total)))
    assert seen
    assert seen[-1][0] == seen[-1][1] == 3


# ── vector_index ───────────────────────────────────────────────────────────

def test_hashing_embedding_is_deterministic_and_normalized():
    embedder = HashingEmbedder(dim=256)
    first = embedder.embed("Kedi sıcak bir yer arar.")
    second = embedder.embed("Kedi sıcak bir yer arar.")
    other = embedder.embed("Fatura toplamı 1200 TL.")

    assert first == second
    assert first != other
    assert math.isclose(sum(value * value for value in first), 1.0, rel_tol=1e-9)
    assert all(value >= 0 for value in first)


def test_vector_search_ranks_the_relevant_chunk():
    chunks = [
        DocumentChunk("c1", 1, "The invoice total is 1200 TL."),
        DocumentChunk("c2", 2, "Cats sleep most of the day."),
        DocumentChunk("c3", 3, "The support line opens at nine."),
    ]
    index = VectorIndex(chunks)

    hits = index.search("invoice total", top_k=2)

    assert hits
    assert hits[0].chunk_id == "c1"
    assert hits[0].page_number == 1
    assert hits[0].score > 0
    assert index.backend in {"numpy", "faiss", "python"}


def test_vector_search_handles_empty_input():
    assert VectorIndex([]).search("anything") == []
    assert VectorIndex([DocumentChunk("c1", 1, "text")]).search("   ") == []
    assert VectorIndex([DocumentChunk("c1", 1, "text")]).search("x", min_score=0.9) == []


# ── local_llm ──────────────────────────────────────────────────────────────

class _FakeModel:
    def __init__(self, cancel_flag=None):
        self.cancel_flag = cancel_flag
        self.prompts = []

    def __call__(self, prompt, **kwargs):
        self.prompts.append((prompt, kwargs))
        if self.cancel_flag is not None:
            def stream():
                yield {"choices": [{"text": "first"}]}
                self.cancel_flag[0] = True
                yield {"choices": [{"text": "second"}]}
            return stream()
        return iter([
            {"choices": [{"text": "Merhaba "}]},
            {"choices": [{"text": "dünya", "finish_reason": "stop"}]},
        ])


def _gguf(tmp_path):
    path = tmp_path / "model.gguf"
    path.write_bytes(b"gguf")
    return str(path)


def test_missing_model_returns_none(tmp_path):
    llm = LocalLLM(model_path=str(tmp_path / "yok.gguf"))
    assert not llm.available
    assert llm.generate("hello") is None
    assert create_local_llm(str(tmp_path / "yok.gguf")) is None


def test_model_path_is_discovered_through_model_manager(tmp_path, monkeypatch):
    gguf = _gguf(tmp_path)

    class FakeManager:
        model_root = tmp_path / "models"
        app_root = staticmethod(lambda: tmp_path)

        def configured_paths(self):
            return {"llm": gguf}

    monkeypatch.setattr(local_llm, "ModelManager", FakeManager)

    llm = LocalLLM()

    assert llm.available
    assert llm.model_path == gguf


def test_fake_runtime_streams_an_answer(tmp_path):
    model = _FakeModel()
    llm = LocalLLM(_gguf(tmp_path), model_factory=lambda **kwargs: model)

    assert llm.available
    assert llm.generate("Soru?", max_tokens=10) == "Merhaba dünya"
    assert model.prompts[0][1]["stream"] is True


def test_generation_can_be_cancelled(tmp_path):
    flag = [False]
    model = _FakeModel(cancel_flag=flag)
    llm = LocalLLM(_gguf(tmp_path), model_factory=lambda **kwargs: model)

    with pytest.raises(CancelledError):
        llm.generate("Soru?", cancel=lambda: flag[0])


def test_missing_llama_cpp_degrades_to_none(tmp_path, monkeypatch):
    monkeypatch.setattr(local_llm, "_import_llama_cpp", lambda: None)
    llm = LocalLLM(_gguf(tmp_path))

    assert llm.generate("hello") is None
    assert "llama" in llm.last_error.lower()


# ── rag_engine ─────────────────────────────────────────────────────────────

class _FakeLLM:
    available = True

    def __init__(self, answer):
        self.answer = answer
        self.prompts = []

    def generate(self, prompt, **kwargs):
        self.prompts.append(prompt)
        if kwargs.get("progress"):
            kwargs["progress"](1, 1, "ok")
        return self.answer


def test_ask_with_llm_returns_page_sources(faq_pdf, tmp_path):
    llm = _FakeLLM("The invoice total is 1200 TL.")
    engine = RagEngine(llm=llm, cache_dir=tmp_path / "cache")

    result = engine.ask(faq_pdf, "What is the invoice total?")

    assert result.found
    assert result.used_llm
    assert result.answer == "The invoice total is 1200 TL."
    assert result.sources
    assert result.sources[0].page_number == 1
    assert "invoice" in result.sources[0].quote.casefold()
    assert "Sayfa 1" in llm.prompts[0]
    assert "invoice total" in llm.prompts[0].casefold()


def test_ask_without_llm_gives_an_extractive_answer(faq_pdf, tmp_path):
    engine = RagEngine(use_llm=False, cache_dir=tmp_path / "cache")

    result = engine.ask(faq_pdf, "invoice total")

    assert result.found
    assert not result.used_llm
    assert "1200" in result.answer
    assert result.sources[0].page_number == 1


def test_unrelated_question_is_not_answered(faq_pdf, tmp_path):
    engine = RagEngine(use_llm=False, cache_dir=tmp_path / "cache")

    result = engine.ask(faq_pdf, "zebra quantum telescope")

    assert not result.found
    assert result.sources == []
    assert "bulamadım" in result.answer


def test_llm_refusal_is_treated_as_not_found(faq_pdf, tmp_path):
    engine = RagEngine(llm=_FakeLLM("Belgede bulamadım."),
                       cache_dir=tmp_path / "cache")

    result = engine.ask(faq_pdf, "invoice total")

    assert not result.found
    assert result.sources == []
    assert "bulamadım" in result.answer


def test_ask_supports_cancel_and_progress(faq_pdf, tmp_path):
    engine = RagEngine(use_llm=False, cache_dir=tmp_path / "cache")

    with pytest.raises(CancelledError):
        engine.ask(faq_pdf, "invoice", cancel=lambda: True)

    seen = []
    engine.ask(faq_pdf, "invoice", progress=lambda current, total, message="":
               seen.append((current, total)))
    assert seen
    assert seen[-1][0] == 100


def test_second_question_reuses_the_document_cache(faq_pdf, tmp_path):
    engine = RagEngine(use_llm=False, cache_dir=tmp_path / "cache")
    engine.ask(faq_pdf, "invoice total")

    result = engine.ask(faq_pdf, "cats sleep")

    assert result.document is not None
    assert result.document.from_cache
    assert result.sources[0].page_number == 2


def test_module_level_ask_wrapper(faq_pdf, tmp_path):
    result = ask(faq_pdf, "invoice total", use_llm=False,
                 cache_dir=tmp_path / "cache")

    assert result.found
    assert "1200" in result.answer
