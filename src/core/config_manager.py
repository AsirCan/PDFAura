import os
import json
import logging

class ConfigManager:
    """Manages application preferences and recent files history in APPDATA."""
    def __init__(self, app_name="PDFAura"):
        self.app_name = app_name
        self.config_dir = os.path.join(os.getenv('APPDATA', os.path.expanduser('~')), self.app_name)
        self.config_file = os.path.join(self.config_dir, "config.json")
        
        self.default_config = {
            "language": "en",
            "sound_enabled": True,
            "default_output_dir": "",
            "recent_files": [],
            "close_to_tray": True
        }
        
        self.config = self.default_config.copy()
        self.load()

    def load(self):
        try:
            os.makedirs(self.config_dir, exist_ok=True)
            if os.path.exists(self.config_file):
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Merge with defaults to ensure missing keys exist
                    for k, v in data.items():
                        self.config[k] = v
            else:
                self.save()
        except Exception as e:
            logging.error(f"Config yüklenemedi: {e}")

    def save(self):
        try:
            os.makedirs(self.config_dir, exist_ok=True)
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            logging.error(f"Config kaydedilemedi: {e}")

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value
        self.save()

    def add_recent_file(self, file_path):
        if not file_path or not os.path.isfile(file_path):
            return
        
        recent = self.config.get("recent_files", [])
        if file_path in recent:
            recent.remove(file_path)
            
        recent.insert(0, file_path)
        # Keep only last 10
        self.config["recent_files"] = recent[:10]
        self.save()

    def clear_recent_files(self):
        self.config["recent_files"] = []
        self.save()

# Global singleton
cfg = ConfigManager()
