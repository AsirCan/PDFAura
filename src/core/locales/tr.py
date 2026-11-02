"""Turkish translation strings for PDFAura."""


def __getattr__(name):
    if name == "STRINGS":
        from src.core.lang_manager import _STRINGS
        return _STRINGS["tr"]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return ["STRINGS"]
