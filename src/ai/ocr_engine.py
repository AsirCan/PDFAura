from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps

try:
    import pytesseract
except Exception:  # pragma: no cover - optional runtime dependency
    pytesseract = None


class OCREngineUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class OCRWord:
    text: str
    bbox: tuple[float, float, float, float]
    confidence: float | None = None


class OCREngine:
    """Local OCR wrapper used by document intelligence features."""

    def __init__(self, language: str = "tur+eng"):
        self.language = language

    def is_available(self) -> bool:
        return pytesseract is not None and bool(shutil.which("tesseract"))

    def status_message(self) -> str:
        if pytesseract is None:
            return "pytesseract Python paketi bulunamadı."
        if not shutil.which("tesseract"):
            return "Tesseract çalıştırılabilir dosyası PATH içinde bulunamadı."
        return "Tesseract OCR hazır."

    def image_to_text(self, image_path: str, language: str | None = None) -> str:
        if not self.is_available():
            raise OCREngineUnavailable(self.status_message())

        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(image_path)

        with Image.open(path) as image:
            return self.pil_to_text(image, language=language)

    def pil_to_text(self, image: Image.Image, language: str | None = None) -> str:
        if not self.is_available():
            raise OCREngineUnavailable(self.status_message())
        prepared = self.prepare_image(image)
        return self._call_tesseract_text(prepared, language or self.language).strip()

    def pil_to_words(self, image: Image.Image, language: str | None = None) -> list[OCRWord]:
        if not self.is_available():
            raise OCREngineUnavailable(self.status_message())

        prepared = self.prepare_image(image)
        data = self._call_tesseract_data(prepared, language or self.language)
        words: list[OCRWord] = []

        for index, raw_text in enumerate(data.get("text", [])):
            text = str(raw_text).strip()
            if not text:
                continue

            confidence = self._parse_confidence(data.get("conf", [""])[index])
            if confidence is not None and confidence < 0:
                continue

            left = float(data.get("left", [0])[index])
            top = float(data.get("top", [0])[index])
            width = float(data.get("width", [0])[index])
            height = float(data.get("height", [0])[index])
            if width <= 0 or height <= 0:
                continue

            words.append(
                OCRWord(
                    text=text,
                    bbox=(left, top, left + width, top + height),
                    confidence=confidence,
                )
            )

        return words

    def prepare_image(self, image: Image.Image) -> Image.Image:
        prepared = image.convert("L")
        prepared = ImageOps.autocontrast(prepared)
        return prepared

    def _call_tesseract_text(self, image: Image.Image, language: str) -> str:
        last_error: Exception | None = None
        for lang in self._language_fallbacks(language):
            try:
                return pytesseract.image_to_string(image, lang=lang)
            except Exception as exc:  # pragma: no cover - depends on local OCR data
                last_error = exc
        raise OCREngineUnavailable(f"OCR çalıştırılamadı: {last_error}")

    def _call_tesseract_data(self, image: Image.Image, language: str) -> dict:
        last_error: Exception | None = None
        for lang in self._language_fallbacks(language):
            try:
                return pytesseract.image_to_data(
                    image,
                    lang=lang,
                    output_type=pytesseract.Output.DICT,
                )
            except Exception as exc:  # pragma: no cover - depends on local OCR data
                last_error = exc
        raise OCREngineUnavailable(f"OCR koordinatları çıkarılamadı: {last_error}")

    def _language_fallbacks(self, language: str) -> tuple[str | None, ...]:
        languages: list[str | None] = []
        if language:
            languages.append(language)
            if "+" in language:
                languages.extend(part for part in language.split("+") if part)
        languages.extend(["eng", None])

        unique: list[str | None] = []
        seen = set()
        for lang in languages:
            key = lang or "__default__"
            if key not in seen:
                seen.add(key)
                unique.append(lang)
        return tuple(unique)

    @staticmethod
    def _parse_confidence(value) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
