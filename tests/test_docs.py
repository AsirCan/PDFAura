"""Tests verifying documentation and web landing page integrity.

Verifies:
1. docs/USER_GUIDE.md covers all tools mentioned in eklenecekler.md in Turkish & English.
2. docs/index.html is a valid, modern, responsive, standalone landing page with
   dark/light theme, FAQ accordion, feature cards, download buttons, and privacy highlights.
"""

from html.parser import HTMLParser
import os
import re

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS_DIR = os.path.join(ROOT_DIR, "docs")
USER_GUIDE_PATH = os.path.join(DOCS_DIR, "USER_GUIDE.md")
INDEX_HTML_PATH = os.path.join(DOCS_DIR, "index.html")


# ── Simple HTML Inspector without third-party dependencies ──────────────────


class _MetaTagParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta_tags = []
        self.links = []
        self.buttons = []
        self.headings = []
        self.tags = set()
        self._current_tag = None
        self._current_text = []

    def handle_starttag(self, tag, attrs):
        self.tags.add(tag.lower())
        attrs_dict = dict(attrs)
        if tag.lower() == "meta":
            self.meta_tags.append(attrs_dict)
        elif tag.lower() == "a":
            self.links.append(attrs_dict)
        elif tag.lower() == "button":
            self.buttons.append(attrs_dict)

        if tag.lower() in ("h1", "h2", "h3", "h4"):
            self._current_tag = tag.lower()
            self._current_text = []

    def handle_endtag(self, tag):
        if tag.lower() == self._current_tag:
            self.headings.append((self._current_tag, "".join(self._current_text).strip()))
            self._current_tag = None
            self._current_text = []

    def handle_data(self, data):
        if self._current_tag:
            self._current_text.append(data)


# ── USER_GUIDE.md Tests ─────────────────────────────────────────────────────


def test_user_guide_file_exists():
    assert os.path.isfile(USER_GUIDE_PATH), f"USER_GUIDE.md not found at {USER_GUIDE_PATH}"
    with open(USER_GUIDE_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    assert len(content.strip()) > 500, "USER_GUIDE.md should not be empty"


def test_user_guide_bilingual():
    """Ensure both Turkish and English major sections are present."""
    with open(USER_GUIDE_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    # Turkish section check
    assert "Türkçe Kullanım Kılavuzu" in content or "Bölüm 1: Türkçe" in content
    # English section check
    assert "English User Guide" in content or "Part 2: English" in content


def test_user_guide_covers_all_tools():
    """Verify that all tools in eklenecekler.md and user prompt are documented."""
    with open(USER_GUIDE_PATH, "r", encoding="utf-8") as f:
        text = f.read().lower()

    required_topics = [
        # (Topic name, keywords that must appear)
        ("Compress", ["compress", "sıkıştır"]),
        ("Split", ["split", "böl"]),
        ("Merge", ["merge", "birleştir"]),
        ("Convert", ["convert", "dönüştür", "word"]),
        ("OCR", ["ocr", "tesseract", "searchable"]),
        ("Security", ["security", "şifre", "encrypt", "filigran", "watermark"]),
        ("Redaction", ["redact", "sansür"]),
        ("Scan Quality", ["scanner", "tarayıcı", "kalite", "quality", "laplacian"]),
        ("AI Chat & RAG", ["chat", "sohbet", "rag", "kaynak"]),
        ("Summarizer", ["summar", "özet"]),
        ("Compare", ["compare", "karşılaştır"]),
        ("Smart Naming", ["nam", "adlandırma"]),
        ("Student Mode", ["student", "öğrenci", "flashcard", "soru"]),
        ("Presentation", ["presentation", "sunum", "pptx", "slayt"]),
        ("CLI", ["cli", "python -m src.cli", "komut satırı"]),
        ("Page Editing", ["rotate", "döndür", "delete", "sil", "reorder", "sıral"]),
        ("Batch", ["batch", "toplu"]),
    ]

    for topic, keywords in required_topics:
        found = any(k in text for k in keywords)
        assert found, f"Topic '{topic}' with keywords {keywords} not found in USER_GUIDE.md"


def test_user_guide_cli_code_examples():
    """Check that CLI syntax examples and commands are documented."""
    with open(USER_GUIDE_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    assert "python -m src.cli" in content
    assert "compress" in content
    assert "split" in content
    assert "merge" in content
    assert "encrypt" in content


# ── index.html Tests ────────────────────────────────────────────────────────


def test_index_html_file_exists():
    assert os.path.isfile(INDEX_HTML_PATH), f"index.html not found at {INDEX_HTML_PATH}"
    with open(INDEX_HTML_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    assert len(content.strip()) > 500, "index.html should not be empty"


def test_index_html_valid_structure():
    with open(INDEX_HTML_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    assert "<!DOCTYPE html>" in content or "<!doctype html>" in content.lower()
    assert "<html" in content
    assert "<head>" in content or "<head " in content
    assert "<body>" in content or "<body " in content
    assert "</html>" in content


def test_index_html_meta_tags():
    with open(INDEX_HTML_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    parser = _MetaTagParser()
    parser.feed(content)

    meta_dict = {}
    for meta in parser.meta_tags:
        if "name" in meta:
            meta_dict[meta["name"].lower()] = meta.get("content", "")
        if "property" in meta:
            meta_dict[meta["property"].lower()] = meta.get("content", "")
        if "charset" in meta:
            meta_dict["charset"] = meta["charset"].lower()

    # Charset
    assert "charset" in meta_dict and "utf-8" in meta_dict["charset"]

    # Viewport
    assert "viewport" in meta_dict
    assert "width=device-width" in meta_dict["viewport"]

    # Description
    assert "description" in meta_dict
    assert len(meta_dict["description"]) > 20

    # Open Graph tags
    assert "og:title" in meta_dict
    assert "og:description" in meta_dict
    assert "og:type" in meta_dict

    # Twitter card tags
    assert "twitter:card" in meta_dict
    assert "twitter:title" in meta_dict


def test_index_html_theme_support():
    """Verify that light/dark theme support is present."""
    with open(INDEX_HTML_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    # Theme attribute or classes
    assert 'data-theme="dark"' in content or 'data-theme="light"' in content
    assert '[data-theme="dark"]' in content
    assert '[data-theme="light"]' in content
    # Theme toggle button & JS logic
    assert "themeToggle" in content
    assert "localStorage" in content


def test_index_html_feature_cards():
    """Verify that feature cards for core and AI tools exist."""
    with open(INDEX_HTML_PATH, "r", encoding="utf-8") as f:
        content = f.read().lower()

    # Check key feature terms
    features = [
        "sıkıştırma",
        "bölme",
        "birleştirme",
        "dönüştürme",
        "ocr",
        "şifreleme",
        "tarayıcı",
        "sohbet",
        "özet",
        "karşılaştırma",
        "adlandırma",
        "öğrenci",
        "sunum",
        "cli",
        "toplu",
    ]

    for feat in features:
        assert feat in content, f"Feature card for '{feat}' not found in index.html"


def test_index_html_faq_accordion():
    """Verify FAQ accordion elements."""
    with open(INDEX_HTML_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    assert "faq-item" in content
    assert "faq-question" in content
    assert "faq-answer" in content
    assert "aria-expanded" in content
    # Offline FAQ answer check
    assert "offline" in content.lower() or "çevrimdışı" in content.lower()


def test_index_html_download_buttons():
    """Verify download buttons for Windows installer and portable."""
    with open(INDEX_HTML_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    assert "PDFAura_Setup.exe" in content or "setup" in content.lower()
    assert "PDFAura_Portable.zip" in content or "portable" in content.lower()
    assert "v1.0.0" in content


def test_index_html_privacy_first_highlights():
    """Verify privacy-first and local-first messaging."""
    with open(INDEX_HTML_PATH, "r", encoding="utf-8") as f:
        content = f.read().lower()

    assert "yerel" in content or "local" in content
    assert "gizlilik" in content or "privacy" in content
    assert "offline" in content or "çevrimdışı" in content
    assert "aes-256" in content


def test_index_html_standalone():
    """Ensure the landing page is fully standalone without blocking external CDN requirements."""
    with open(INDEX_HTML_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    # Style and script should be embedded directly
    assert "<style>" in content
    assert "<script>" in content
