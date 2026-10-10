# AI Module for PDF Aura
#
# The document Q&A pieces load on first use. Importing them here pulled
# PyMuPDF, numpy and pytesseract into every start of the app, ~150 ms (#25),
# although only the assistant's own modules are needed then.
import importlib

_EXPORTS = {
    "DocumentIndexer": "src.ai.document_indexer",
    "DocumentLoader": "src.ai.document_loader",
    "HashingEmbeddingEngine": "src.ai.embedding_engine",
    "SimpleVectorIndex": "src.ai.vector_index",
}

__all__ = list(_EXPORTS)


def __getattr__(name):
    module = _EXPORTS.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return getattr(importlib.import_module(module), name)
