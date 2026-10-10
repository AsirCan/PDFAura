"""The application layer: what the tools do, and the window around them.

The tools themselves (api, tools, jobs, scanner, assistant, models) use no
UI toolkit and are tested without a window. The window's own side is
window.py (pywebview, the tray, drag and drop), bridge.py (what the page
may call), events.py (what Python tells the page unasked), server.py and
images.py (the page and its pictures) and scanboard.py (the scanner's
pages).
"""
