"""Windows calls the web window needs: the WebView2 runtime check and the
title bar colours. Each does nothing (or says "no") off Windows."""
import logging

# The Evergreen WebView2 runtime's EdgeUpdate client id.
_WEBVIEW2_CLIENT = r"Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
WEBVIEW2_DOWNLOAD = "https://go.microsoft.com/fwlink/p/?LinkId=2124703"

# DwmSetWindowAttribute ids: immersive dark mode (20 since Windows 10 20H1,
# 19 before), caption and caption-text colour (Windows 11).
_DWMWA_USE_IMMERSIVE_DARK_MODE = (20, 19)
_DWMWA_CAPTION_COLOR = 35
_DWMWA_TEXT_COLOR = 36


def webview2_version():
    """The installed WebView2 runtime's version, or None.

    pywebview only logs a warning and falls back to Internet Explorer's
    engine (MSHTML) when it is missing, so the app looks for it first.
    """
    try:
        import winreg
    except ImportError:
        return None
    for hive, prefix in ((winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node"),
                         (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE"),
                         (winreg.HKEY_CURRENT_USER, r"SOFTWARE")):
        try:
            with winreg.OpenKey(hive, rf"{prefix}\{_WEBVIEW2_CLIENT}") as key:
                version, _kind = winreg.QueryValueEx(key, "pv")
        except OSError:
            continue
        if version and version != "0.0.0.0":
            return version
    return None


def _colorref(color):
    color = color.lstrip("#")
    red, green, blue = (int(color[i:i + 2], 16) for i in (0, 2, 4))
    return red | (green << 8) | (blue << 16)


def style_title_bar(hwnd, dark, caption, text):
    """Dark or light title bar, and on Windows 11 the window's own canvas
    colour, so bar and window read as one surface."""
    try:
        import ctypes
        from ctypes import wintypes
        set_attribute = ctypes.windll.dwmapi.DwmSetWindowAttribute
        set_attribute.argtypes = (wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD)
        value = ctypes.c_int(1 if dark else 0)
        for attribute in _DWMWA_USE_IMMERSIVE_DARK_MODE:
            if set_attribute(hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value)) == 0:
                break
        for attribute, color in ((_DWMWA_CAPTION_COLOR, caption), (_DWMWA_TEXT_COLOR, text)):
            ref = wintypes.DWORD(_colorref(color))
            set_attribute(hwnd, attribute, ctypes.byref(ref), ctypes.sizeof(ref))
        # Windows 10 repaints the frame only when told it changed.
        flags = 0x0001 | 0x0002 | 0x0004 | 0x0010 | 0x0020   # NOSIZE|NOMOVE|NOZORDER|NOACTIVATE|FRAMECHANGED
        ctypes.windll.user32.SetWindowPos(hwnd, None, 0, 0, 0, 0, flags)
    except Exception:
        logging.getLogger(__name__).debug("Title bar not styled", exc_info=True)


def show_error(title, text):
    """A native message box, for when there is no window to show it in."""
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, text, title, 0x10)
    except Exception:
        print(f"{title}: {text}")
