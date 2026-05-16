from __future__ import annotations

import os
import shutil
import subprocess
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from src.core.config_manager import cfg


ProgressCallback = Callable[[int, int], None]


@dataclass(frozen=True)
class ModelSpec:
    id: str
    name: str
    category: str
    description: str
    relative_dir: str
    filenames: tuple[str, ...] = ()
    patterns: tuple[str, ...] = ()
    size_mb: float = 0.0
    required: bool = False
    license_name: str = ""
    source_url: str = ""
    download_url: str = ""
    hardware_profile: str = "Hafif"
    notes: str = ""


@dataclass(frozen=True)
class ModelStatus:
    spec: ModelSpec
    installed: bool
    path: str
    message: str
    size_mb: float = 0.0


class ModelDownloadError(RuntimeError):
    pass


DEFAULT_MODEL_SPECS: tuple[ModelSpec, ...] = (
    ModelSpec(
        id="scanner_u2netp",
        name="Belge Kenar Modeli - Hafif ONNX",
        category="vision",
        description="Tarama ekranında belge sınırlarını local ONNX modeliyle bulmak için kullanılır.",
        relative_dir="vision",
        filenames=("u2netp_document.onnx",),
        size_mb=4.7,
        required=True,
        license_name="Model kaynağına göre kontrol edilmeli",
        source_url="https://huggingface.co/chwshuang/Stable_diffusion_remove_background_model",
        download_url="https://huggingface.co/chwshuang/Stable_diffusion_remove_background_model/resolve/main/u2netp.onnx",
        hardware_profile="Hafif",
        notes="Mevcut scanner algoritmasının hızlı AI fallback modelidir.",
    ),
    ModelSpec(
        id="local_llm",
        name="Yerel LLM - Qwen/Mistral GGUF",
        category="llm",
        description="PDF sohbeti, özet, komut anlama ve öğrenci modu için kullanılacak yerel dil modeli.",
        relative_dir="llm",
        patterns=("*.gguf",),
        size_mb=900.0,
        required=True,
        license_name="Seçilen modele göre değişir; ticari kullanım ayrıca doğrulanmalı",
        source_url="https://huggingface.co/models?search=gguf%20qwen%20instruct",
        hardware_profile="Hafif/Standart",
        notes="İlk hedef küçük/orta boy Qwen veya Mistral instruct GGUF modelidir.",
    ),
    ModelSpec(
        id="embedding_model",
        name="Yerel Embedding Modeli",
        category="embeddings",
        description="PDF parçalarını vektörleştirip kaynak gösteren yerel arama/RAG sistemi için kullanılır.",
        relative_dir="embeddings",
        patterns=("*.onnx", "*.bin", "*.safetensors", "*.gguf"),
        size_mb=120.0,
        required=True,
        license_name="Seçilen modele göre değişir; ticari kullanım ayrıca doğrulanmalı",
        source_url="https://huggingface.co/models?search=multilingual%20embedding",
        hardware_profile="Hafif",
        notes="Küçük multilingual embedding modeli tercih edilecek.",
    ),
    ModelSpec(
        id="ocr_engine",
        name="Yerel OCR - Tesseract/PaddleOCR",
        category="ocr",
        description="Taranmış PDF ve fotoğraf tabanlı belgelerden metin çıkarmak için kullanılır.",
        relative_dir="ocr",
        patterns=("*.onnx", "*.pdmodel", "*.traineddata"),
        size_mb=80.0,
        required=True,
        license_name="Tesseract Apache-2.0; PaddleOCR Apache-2.0",
        source_url="https://tesseract-ocr.github.io/tessdoc/Installation.html",
        hardware_profile="Hafif",
        notes="Tesseract sistemde kuruluysa model dosyası seçmeden hazır kabul edilir.",
    ),
    ModelSpec(
        id="speech_whisper",
        name="Yerel Ses Tanıma - faster-whisper",
        category="speech",
        description="Sesli asistan komutlarını tamamen local olarak metne dönüştürür.",
        relative_dir="speech",
        patterns=("*.bin", "*.onnx", "*.ct2", "model.bin"),
        size_mb=460.0,
        required=False,
        license_name="Whisper/faster-whisper model lisansı kontrol edilmeli",
        source_url="https://huggingface.co/Systran/faster-whisper-small",
        hardware_profile="Standart",
        notes="Mevcut sesli asistan small modeli lazy-load eder; model yoksa uygulama açılışını bozmaz.",
    ),
)


class ModelManager:
    """Local AI model discovery, configuration and download helper."""

    def __init__(self, model_root: str | None = None):
        configured_root = model_root or cfg.get("ai_model_root", "")
        self.model_root = Path(configured_root).expanduser() if configured_root else self.default_model_root()
        self.model_root = self.model_root.resolve()

    @staticmethod
    def app_root() -> Path:
        return Path(__file__).resolve().parents[2]

    @staticmethod
    def default_model_root() -> Path:
        return Path(cfg.config_dir).expanduser().resolve() / "models"

    def set_model_root(self, path: str):
        self.model_root = Path(path).expanduser().resolve()
        cfg.set("ai_model_root", str(self.model_root))
        self.ensure_directories()

    def ensure_directories(self):
        last_error = None
        for root in self._writable_root_candidates():
            try:
                root.mkdir(parents=True, exist_ok=True)
                for spec in DEFAULT_MODEL_SPECS:
                    (root / spec.relative_dir).mkdir(parents=True, exist_ok=True)
                self.model_root = root.resolve()
                return
            except OSError as exc:
                last_error = exc
        if last_error:
            raise last_error

    def _writable_root_candidates(self) -> list[Path]:
        candidates = [self.model_root]

        local_appdata = os.getenv("LOCALAPPDATA")
        if local_appdata:
            candidates.append(Path(local_appdata) / "PDFAura" / "models")

        user_home = Path(os.path.expanduser("~"))
        candidates.append(user_home / ".pdfaura" / "models")
        candidates.append(self.app_root() / "models")
        candidates.append(Path.cwd() / "models")

        unique = []
        seen = set()
        for path in candidates:
            resolved_key = str(path)
            if resolved_key not in seen:
                seen.add(resolved_key)
                unique.append(path)
        return unique

    def get_spec(self, model_id: str) -> ModelSpec | None:
        for spec in DEFAULT_MODEL_SPECS:
            if spec.id == model_id:
                return spec
        return None

    def configured_paths(self) -> dict:
        paths = cfg.get("ai_model_paths", {})
        return paths if isinstance(paths, dict) else {}

    def set_model_path(self, model_id: str, path: str):
        paths = self.configured_paths()
        paths[model_id] = path
        cfg.set("ai_model_paths", paths)

    def clear_model_path(self, model_id: str):
        paths = self.configured_paths()
        if model_id in paths:
            del paths[model_id]
            cfg.set("ai_model_paths", paths)

    def model_dir(self, spec: ModelSpec) -> Path:
        return self.model_root / spec.relative_dir

    def status(self, model_id: str) -> ModelStatus:
        spec = self.get_spec(model_id)
        if not spec:
            raise KeyError(model_id)
        return self._status_for_spec(spec)

    def all_statuses(self) -> list[ModelStatus]:
        self.ensure_directories()
        return [self._status_for_spec(spec) for spec in DEFAULT_MODEL_SPECS]

    def _status_for_spec(self, spec: ModelSpec) -> ModelStatus:
        if spec.id == "ocr_engine":
            tesseract_path = shutil.which("tesseract")
            if tesseract_path:
                return ModelStatus(spec, True, tesseract_path, "Tesseract PATH üzerinden hazır.", 0.0)

        configured = self.configured_paths().get(spec.id, "")
        if configured:
            found = self._find_in_path(spec, Path(configured).expanduser())
            if found:
                return self._installed_status(spec, found, "Kullanıcı tarafından seçilen model hazır.")
            return ModelStatus(spec, False, configured, "Seçilen model yolu bulunamadı veya okunamıyor.")

        found = self._find_in_candidates(spec)
        if found:
            return self._installed_status(spec, found, "Model bulundu.")

        return ModelStatus(spec, False, "", "Model eksik. Yol seçin veya indirme/kaynak sayfasını açın.")

    def _installed_status(self, spec: ModelSpec, path: Path, message: str) -> ModelStatus:
        size_mb = 0.0
        try:
            if path.is_file():
                size_mb = path.stat().st_size / (1024 * 1024)
            elif path.is_dir():
                size_mb = sum(p.stat().st_size for p in path.rglob("*") if p.is_file()) / (1024 * 1024)
        except OSError:
            size_mb = 0.0
        return ModelStatus(spec, True, str(path), message, size_mb)

    def _candidate_dirs(self, spec: ModelSpec) -> Iterable[Path]:
        roots = [
            self.model_root / spec.relative_dir,
            self.app_root() / "models" / spec.relative_dir,
        ]
        if spec.filenames:
            roots.extend([
                self.model_root,
                self.app_root() / "models",
            ])

        meipass = getattr(sys, "_MEIPASS", "")
        if meipass:
            roots.append(Path(meipass) / "models" / spec.relative_dir)
            if spec.filenames:
                roots.append(Path(meipass) / "models")

        exe_dir = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else None
        if exe_dir:
            roots.extend([
                exe_dir / "models" / spec.relative_dir,
                exe_dir / "_internal" / "models" / spec.relative_dir,
            ])
            if spec.filenames:
                roots.extend([
                    exe_dir / "models",
                    exe_dir / "_internal" / "models",
                ])

        seen = set()
        for root in roots:
            key = str(root)
            if key not in seen:
                seen.add(key)
                yield root

    def _find_in_candidates(self, spec: ModelSpec) -> Path | None:
        for root in self._candidate_dirs(spec):
            found = self._find_in_path(spec, root)
            if found:
                return found
        return None

    def _find_in_path(self, spec: ModelSpec, path: Path) -> Path | None:
        if path.is_file():
            if spec.filenames and path.name in spec.filenames:
                return path
            if any(path.match(pattern) for pattern in spec.patterns):
                return path
            return path if not spec.filenames and not spec.patterns else None

        if not path.is_dir():
            return None

        for filename in spec.filenames:
            candidate = path / filename
            if candidate.is_file():
                return candidate

        for pattern in spec.patterns:
            matches = sorted(path.glob(pattern))
            if matches:
                return matches[0]
        return None

    def download_model(self, model_id: str, progress: ProgressCallback | None = None) -> Path:
        spec = self.get_spec(model_id)
        if not spec:
            raise ModelDownloadError(f"Bilinmeyen model: {model_id}")
        if not spec.download_url:
            raise ModelDownloadError("Bu model için doğrudan indirme bağlantısı tanımlı değil.")
        if not spec.filenames:
            raise ModelDownloadError("Bu model için hedef dosya adı tanımlı değil.")

        self.ensure_directories()
        destination = self.model_dir(spec) / spec.filenames[0]
        part = destination.with_suffix(destination.suffix + ".part")

        try:
            req = urllib.request.Request(spec.download_url, headers={"User-Agent": "PDFAura/1.0"})
            with urllib.request.urlopen(req, timeout=30) as response:
                total = int(response.headers.get("Content-Length", 0))
                downloaded = 0
                with open(part, "wb") as handle:
                    while True:
                        chunk = response.read(1024 * 128)
                        if not chunk:
                            break
                        handle.write(chunk)
                        downloaded += len(chunk)
                        if progress:
                            progress(downloaded, total)
            part.replace(destination)
            return destination
        except Exception as exc:
            try:
                if part.exists():
                    part.unlink()
            except OSError:
                pass
            raise ModelDownloadError(str(exc)) from exc

    def test_model(self, model_id: str) -> tuple[bool, str]:
        status = self.status(model_id)
        if not status.installed:
            return False, status.message

        if model_id == "ocr_engine" and status.path.lower().endswith("tesseract.exe"):
            try:
                result = subprocess.run(
                    [status.path, "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                )
                first_line = (result.stdout or result.stderr).splitlines()[0]
                return result.returncode == 0, first_line or "Tesseract test edildi."
            except Exception as exc:
                return False, f"OCR testi başarısız: {exc}"

        path = Path(status.path)
        try:
            if path.is_file():
                with open(path, "rb") as handle:
                    handle.read(1)
                return True, f"Model dosyası okunabiliyor: {path.name}"
            if path.is_dir():
                files = [p for p in path.rglob("*") if p.is_file()]
                return bool(files), f"Model klasörü okunabiliyor. Dosya sayısı: {len(files)}"
        except OSError as exc:
            return False, f"Model okunamadı: {exc}"

        return False, "Model yolu geçersiz."
