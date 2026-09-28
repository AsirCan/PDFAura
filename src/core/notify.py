"""Completion sounds, honouring the "play a sound when a job finishes" setting.

The setting was saved but never read anywhere, so ticking it did nothing.
"""
import sys

from src.core.config_manager import cfg


def _beep(sound_type):
    if not cfg.get("sound_enabled", True):
        return
    if sys.platform != "win32":
        return
    try:
        import winsound
        winsound.MessageBeep(sound_type)
    except Exception:
        pass   # a missing sound device must never break an operation


def play_success():
    try:
        import winsound
        _beep(winsound.MB_ICONASTERISK)
    except ImportError:
        pass


def play_error():
    try:
        import winsound
        _beep(winsound.MB_ICONHAND)
    except ImportError:
        pass
