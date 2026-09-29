import json
import locale
import logging
import os
import shutil
import tempfile


# Windows primary language IDs (LANGID & 0x3FF) for the UI languages.
_WINDOWS_LANGUAGE_IDS = {
    0x1F: "tr", 0x09: "en", 0x04: "zh", 0x39: "hi", 0x0A: "es", 0x01: "ar",
    0x0C: "fr", 0x45: "bn", 0x16: "pt", 0x19: "ru", 0x20: "ur", 0x21: "id",
    0x07: "de", 0x11: "ja",
}


def detect_default_language():
    """Pick the starting language from the Windows UI language.

    The stored default was "en" while get_text() fell back to "tr", so a
    fresh install disagreed with itself. A Windows language the app does not
    speak gets English.
    """
    try:
        import ctypes
        language_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        return _WINDOWS_LANGUAGE_IDS.get(language_id & 0x3FF, "en")
    except Exception:
        pass
    try:
        code = (locale.getdefaultlocale()[0] or "")
    except Exception:
        code = ""
    code = code.lower()[:2]
    return code if code in _WINDOWS_LANGUAGE_IDS.values() else "en"


class ConfigManager:
    """Manages application preferences and recent files history in APPDATA."""

    MAX_RECENT_FILES = 10

    def __init__(self, app_name="PDFAura"):
        self.app_name = app_name
        self.config_dir = os.path.join(os.getenv('APPDATA', os.path.expanduser('~')), self.app_name)
        self.config_file = os.path.join(self.config_dir, "config.json")

        self.default_config = {
            "language": detect_default_language(),
            "sound_enabled": True,
            "default_output_dir": "",
            "recent_files": [],
            "close_to_tray": True,
            "theme": "system",             # "system", "paper" (light) or "night" (dark)
            "ai_model_root": "",
            "ai_model_paths": {},
            "scanner_session_enabled": True,
            "scanner_strip_width": 0,      # 0 = auto (fit beside the photo)
        }

        self.config = self.default_config.copy()
        self.load()

    def load(self):
        try:
            os.makedirs(self.config_dir, exist_ok=True)
            if not os.path.exists(self.config_file):
                self.save()
                return
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                # Keep the broken file instead of silently overwriting it, so
                # the settings can be recovered by hand.
                self._back_up_corrupt_file(exc)
                self.save()
                return
            if isinstance(data, dict):
                for key, value in data.items():
                    self.config[key] = value
        except Exception as e:
            logging.error(f"Config yüklenemedi: {e}")

    def _back_up_corrupt_file(self, exc):
        backup = self.config_file + ".corrupt"
        try:
            shutil.copy2(self.config_file, backup)
            logging.error(f"config.json okunamadı ({exc}); yedek: {backup}")
        except Exception as copy_error:
            logging.error(f"Bozuk config yedeklenemedi: {copy_error}")

    def save(self):
        """Write the config atomically, so a crash cannot truncate it."""
        try:
            os.makedirs(self.config_dir, exist_ok=True)
            handle, temp_path = tempfile.mkstemp(prefix=".config-", suffix=".json",
                                                 dir=self.config_dir)
            try:
                with os.fdopen(handle, "w", encoding="utf-8") as f:
                    json.dump(self.config, f, indent=4)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(temp_path, self.config_file)
            except Exception:
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except OSError:
                        pass
                raise
        except Exception as e:
            logging.error(f"Config kaydedilemedi: {e}")

    @property
    def scanner_session_dir(self):
        """%APPDATA%\\PDFAura\\scanner_session – Belge Tarayıcı'nın yarım kalan işi."""
        return os.path.join(self.config_dir, "scanner_session")

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value
        self.save()

    def add_recent_file(self, file_path):
        """Remember a file the user just produced or opened."""
        if not file_path or not os.path.isfile(file_path):
            return

        file_path = os.path.abspath(file_path)
        recent = [p for p in self.config.get("recent_files", [])
                  if os.path.normcase(p) != os.path.normcase(file_path)]
        recent.insert(0, file_path)
        self.config["recent_files"] = recent[:self.MAX_RECENT_FILES]
        self.save()

    def get_recent_files(self):
        """Recent files that still exist on disk."""
        return [p for p in self.config.get("recent_files", []) if os.path.isfile(p)]

    def clear_recent_files(self):
        self.config["recent_files"] = []
        self.save()


# Global singleton
cfg = ConfigManager()
