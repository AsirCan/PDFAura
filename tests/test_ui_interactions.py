"""Drive the real main window: navigation, shortcuts, mode pickers, a full
tool run with its result panel, the preview, the assistant bar and resizing.

The window is built once on the shared Tk root; each test leaves it on a
known page. Worker threads are replaced where a real run needs Ghostscript.
"""
import os
import shutil
import time
import tkinter as tk
from tkinter import ttk

import pytest

from src.core.lang_manager import _
from conftest import make_pdf


def pump(root, seconds=0.05):
    """Run the real event loop briefly. Worker threads post results with
    after(), which only works while mainloop() is running."""
    root.after(int(seconds * 1000), root.quit)
    root.mainloop()


def wait_for(root, condition, timeout=5.0):
    end = time.time() + timeout

    def check():
        if condition() or time.time() >= end:
            root.quit()
        else:
            root.after(20, check)

    root.after(20, check)
    root.mainloop()
    return condition()


@pytest.fixture(scope="module")
def app(tk_root):
    from src.core.config_manager import cfg
    cfg.config["close_to_tray"] = False
    from src.gui.main_window import MainWindow
    for child in tk_root.winfo_children():
        child.destroy()
    tk_root.deiconify()
    window = MainWindow(tk_root)
    tk_root.geometry("1480x920+0+0")
    pump(tk_root, 0.2)
    yield tk_root, window
    for child in tk_root.winfo_children():
        child.destroy()
    tk_root.withdraw()


def buttons_under(widget):
    for child in widget.winfo_children():
        if isinstance(child, ttk.Button):
            yield child
        yield from buttons_under(child)


def surface_colour(widget):
    from src.gui.styles import surface_of
    return str(surface_of(widget)).upper()


# ── Navigation ──────────────────────────────────────────────────────────────

PAGES = ["compress", "organize", "scanner", "convert", "security", "advanced", "batch"]


@pytest.mark.parametrize("page", PAGES)
def test_every_nav_button_opens_its_page(app, page):
    root, window = app
    window.nav_buttons[page].invoke()
    pump(root)
    assert window.current_page == page
    assert wait_for(root, lambda: window.workspaces[page].frame.winfo_ismapped(), timeout=2)
    selected = [k for k, b in window.nav_buttons.items() if b.instate(["selected"])]
    assert selected == [page]
    eyebrow, title, _body = __import__("src.gui.main_window", fromlist=["PAGE_META_KEYS"]).PAGE_META_KEYS[page]
    assert window.page_title_var.get() == _(title)


@pytest.mark.parametrize("index,page", list(enumerate(PAGES, start=1)))
def test_ctrl_number_switches_tools(app, index, page):
    root, window = app
    window.show_page("compress" if page != "compress" else "batch")
    root.focus_force()
    root.event_generate(f"<Control-Key-{index}>")
    pump(root)
    assert window.current_page == page


def test_ctrl_k_focuses_the_assistant(app):
    root, window = app
    window.show_page("compress")
    root.focus_force()
    pump(root)
    window.focus_assistant()
    pump(root)
    assert root.focus_get() is window.txt_chat
    assert window.txt_chat.get() == ""                      # placeholder cleared
    assert window.command_bar.cget("style") == "CommandFocus.TFrame"
    root.focus_set()
    pump(root)
    assert window.txt_chat.get() == window.chat_placeholder  # placeholder back
    assert window.txt_chat.cget("style") == "CommandHint.TEntry"


def test_group_segments_switch_split_merge_edit(app):
    root, window = app
    window.show_page("organize")
    group = window.workspaces["organize"]
    for key in ("merge", "edit", "split"):
        group.buttons[key].invoke()
        pump(root)
        assert group.current_key == key
        assert wait_for(root, lambda: group.groups[key].frame.winfo_ismapped(), timeout=2)
        assert [k for k, b in group.buttons.items() if b.instate(["selected"])] == [key]


# ── Mode pickers ────────────────────────────────────────────────────────────

def test_edit_modes_show_their_own_fields(app):
    root, window = app
    window.show_page("organize")
    window.workspaces["organize"].show("edit")
    tab = window.get_active_tab()
    for label, frame in tab.edit_frames.items():
        tab.edit_mode_picker.buttons[label].invoke()
        assert tab.edit_mode_var.get() == label
        assert wait_for(root, lambda: frame.winfo_ismapped(), timeout=2)
        assert [f for f in tab.edit_frames.values() if f.winfo_ismapped()] == [frame]


def test_security_confirm_field_only_when_encrypting(app):
    root, window = app
    window.show_page("security")
    tab = window.get_active_tab()
    picker = tab.mode_picker
    picker.buttons[_("security_encrypt")].invoke()
    assert wait_for(root, lambda: tab.confirm_row.winfo_ismapped(), timeout=2)
    picker.buttons[_("security_decrypt")].invoke()
    assert wait_for(root, lambda: not tab.confirm_row.winfo_ismapped(), timeout=2)
    assert tab.password_frame.winfo_ismapped()
    picker.buttons[_("security_watermark")].invoke()
    assert wait_for(root, lambda: tab.watermark_frame.winfo_ismapped(), timeout=2)
    assert not tab.password_frame.winfo_ismapped()
    picker.buttons[_("security_encrypt")].invoke()
    assert wait_for(root, lambda: tab.confirm_row.winfo_ismapped(), timeout=2)


def test_convert_picker_shows_every_mode_and_wraps(app):
    root, window = app
    window.show_page("convert")
    tab = window.get_active_tab()
    picker = tab.convert_mode_picker
    assert len(picker.buttons) == 7
    for label, frame in tab.convert_frames.items():
        picker.buttons[label].invoke()
        assert wait_for(root, lambda: frame.winfo_ismapped(), timeout=2), label
    rows = {int(b.grid_info()["row"]) for b in picker.buttons.values()}
    assert len(rows) >= 2, "seven long labels should wrap onto rows"
    picker.buttons[_("convert_pdf2img")].invoke()
    pump(root)


@pytest.mark.parametrize("page,picker_attr,var_attr", [
    ("batch", "mode_picker", "action_var"),
    ("advanced", "mode_picker", "action_var"),
])
def test_other_pickers_update_their_variable(app, page, picker_attr, var_attr):
    root, window = app
    window.show_page(page)
    tab = window.get_active_tab()
    picker = getattr(tab, picker_attr)
    for label in picker.values:
        picker.buttons[label].invoke()
        assert getattr(tab, var_attr).get() == label
        assert wait_for(root, lambda: tab.frames[label].winfo_ismapped(), timeout=2), label
    picker.buttons[picker.values[0]].invoke()
    pump(root)


def test_compress_quality_is_a_visible_choice(app):
    root, window = app
    window.show_page("compress")
    tab = window.get_active_tab()
    assert len(tab.quality_buttons) == 4
    tab.quality_buttons[0].invoke()
    assert tab._quality_by_label[tab.quality_var.get()] == "screen"
    tab.quality_buttons[1].invoke()
    assert tab._quality_by_label[tab.quality_var.get()] == "ebook"


# ── A full run through a tool ───────────────────────────────────────────────

def test_compress_reports_an_error_without_input(app):
    root, window = app
    window.show_page("compress")
    tab = window.get_active_tab()
    tab.input_var.set("")
    tab.footer.action_button.invoke()
    pump(root)
    assert tab.feedback.tone == "danger"
    assert tab.feedback.message_var.get() == _("err_select_valid_pdf")
    assert not tab.feedback.actions.winfo_ismapped()


def test_compress_success_offers_the_output_and_records_it(app, tmp_path, monkeypatch):
    root, window = app
    import src.gui.tabs.tab_compress as tab_compress

    def fake_compress(src, dst, quality, ctx=None):
        if ctx:
            ctx.report_progress(1, 2, "half")
        time.sleep(0.6)
        shutil.copyfile(src, dst)

    monkeypatch.setattr(tab_compress, "compress_pdf", fake_compress)
    window.show_page("compress")
    tab = window.get_active_tab()
    source = make_pdf(tmp_path / "report.pdf")
    tab.handle_external_drop(source)
    tab.output_var.set(str(tmp_path / "report_small.pdf"))
    tab._output_chosen = True
    pump(root)

    tab.footer.action_button.invoke()
    # Busy: button disabled, progress and cancel shown, panel says so.
    assert tab.footer.action_button.instate(["disabled"])
    assert tab.feedback.tone == "busy"
    assert wait_for(root, lambda: tab.footer.status.winfo_ismapped()
                    and tab.footer.cancel_button.winfo_ismapped(), timeout=0.5)

    assert wait_for(root, lambda: tab.feedback.tone == "success")
    # The panel grows; the scroll area re-measures within a few frames.
    assert wait_for(root, lambda: tab.feedback.actions.winfo_ismapped(), timeout=2)
    # ...and is scrolled into view when the form is taller than the window.
    area = tab.layout.scroll
    if area.is_scrolling:
        assert wait_for(root, lambda: area.canvas.yview()[1] > 0.99, timeout=2)
    assert tab.footer.action_button.instate(["!disabled"])
    assert not tab.footer.cancel_button.winfo_ismapped()
    assert tab.footer.progress_bar.cget("style") == "Done.Horizontal.TProgressbar"
    assert tab.feedback.actions.winfo_ismapped()
    assert tab.feedback.open_file_button.instate(["!disabled"])
    # The sidebar's recent list follows without a restart.
    names = [b.cget("text") for b in buttons_under(window.recent_frame)]
    assert "report_small.pdf" in names


def test_cancel_stops_a_running_job(app, tmp_path, monkeypatch):
    root, window = app
    import src.gui.tabs.tab_compress as tab_compress
    from src.core.task_manager import CancelledError

    def slow_compress(src, dst, quality, ctx=None):
        for _i in range(200):
            if ctx and ctx.is_cancelled:
                raise CancelledError()
            time.sleep(0.01)
        shutil.copyfile(src, dst)

    monkeypatch.setattr(tab_compress, "compress_pdf", slow_compress)
    window.show_page("compress")
    tab = window.get_active_tab()
    tab.handle_external_drop(make_pdf(tmp_path / "a.pdf"))
    tab.output_var.set(str(tmp_path / "b.pdf"))
    tab._output_chosen = True
    tab.footer.action_button.invoke()
    assert wait_for(root, lambda: tab.footer.cancel_button.winfo_ismapped(), timeout=1)
    tab.footer.cancel_button.invoke()
    assert wait_for(root, lambda: tab.feedback.tone == "warning")
    assert tab.feedback.title_var.get() == _("perf_cancelled")
    assert not tab.footer.status.winfo_ismapped()


# ── Result panel & footer ───────────────────────────────────────────────────

def test_feedback_tones_and_actions(app):
    root, window = app
    from src.gui.helpers import InlineFeedback
    frame = ttk.Frame(root, style="Surface.TFrame")
    frame.place(x=0, y=0, width=400, height=300)
    fb = InlineFeedback(frame)
    fb.pack(fill="x")
    pump(root)
    fb.set_info("t", "m")
    assert fb.tone == "info" and not fb.actions.winfo_ismapped()
    fb.set_warning("t", "m", output_path=__file__)
    pump(root)
    assert fb.tone == "warning" and fb.actions.winfo_ismapped()
    fb.set_error("t", "m")
    pump(root)
    assert fb.tone == "danger" and not fb.actions.winfo_ismapped()
    assert fb.badge.cget("text") == _("feedback_error_badge")
    fb.set_cancelled()
    assert fb.badge.cget("text") == _("perf_cancelled_badge")
    frame.destroy()


# ── Preview ─────────────────────────────────────────────────────────────────

def test_preview_follows_the_selected_pdf(app, tmp_path):
    root, window = app
    window.show_page("compress")
    panel = window.preview_panel
    pdf = make_pdf(tmp_path / "preview.pdf", pages=2)
    window.set_preview_file(pdf)
    pump(root, 0.1)
    assert panel.current_path == pdf
    assert panel.tk_image is not None
    assert panel.open_button.instate(["!disabled"])
    assert wait_for(root, lambda: panel.info.winfo_ismapped(), timeout=2)
    assert "2" in panel.meta_var.get()

    window.set_preview_file(None)
    pump(root, 0.1)
    assert panel.current_path is None
    assert panel.open_button.instate(["disabled"])
    assert not panel.info.winfo_ismapped()


def test_preview_opens_the_viewer_and_it_pages_and_zooms(app, tmp_path):
    root, window = app
    pdf = make_pdf(tmp_path / "viewer.pdf", pages=3)
    window.set_preview_file(pdf)
    before = set(root.winfo_children())
    window.preview_panel.open_button.invoke()
    pump(root, 0.2)
    viewer = next(w for w in root.winfo_children() if w not in before and isinstance(w, tk.Toplevel))
    viewer.next_page()
    assert viewer.current_page == 1
    viewer.prev_page()
    assert viewer.current_page == 0
    viewer.zoom_in()
    assert viewer.zoom_label.cget("text") == "150%"
    viewer.zoom_out()
    viewer.event_generate("<Escape>")
    pump(root, 0.1)
    assert not viewer.winfo_exists()
    window.set_preview_file(None)


# ── Lists ───────────────────────────────────────────────────────────────────

def test_merge_empty_hint_comes_and_goes(app, tmp_path):
    root, window = app
    window.show_page("organize")
    window.workspaces["organize"].show("merge")
    tab = window.get_active_tab()
    assert wait_for(root, lambda: tab.empty_hint.label.winfo_ismapped(), timeout=2)
    tab.handle_external_drop(make_pdf(tmp_path / "m1.pdf"))
    pump(root)
    assert not tab.empty_hint.label.winfo_ismapped()
    tab.merge_listbox.selection_set(0)
    tab.merge_remove_btn.invoke()
    assert wait_for(root, lambda: tab.empty_hint.label.winfo_ismapped(), timeout=2)
    window.workspaces["organize"].show("split")


# ── Assistant bar ───────────────────────────────────────────────────────────

def test_assistant_replies_show_and_dismiss(app):
    root, window = app
    window._show_assistant_reply("Merhaba")
    pump(root)
    assert wait_for(root, lambda: window.assistant_reply.winfo_ismapped(), timeout=2)
    assert window.assistant_reply_var.get() == "Merhaba"
    window.hide_assistant_reply()
    pump(root)
    assert not window.assistant_reply.winfo_ismapped()


# ── Dialogs ─────────────────────────────────────────────────────────────────

def test_settings_opens_with_ctrl_comma_and_closes_with_escape(app):
    root, window = app
    before = set(root.winfo_children())
    root.focus_force()
    root.event_generate("<Control-comma>")
    pump(root, 0.3)
    dialogs = [w for w in root.winfo_children() if w not in before and isinstance(w, tk.Toplevel)]
    assert len(dialogs) == 1
    dialog = dialogs[0]
    dialog.focus_force()
    pump(root)
    dialog.event_generate("<Escape>")
    pump(root, 0.1)
    assert not dialog.winfo_exists()


# ── Keyboard focus ring ─────────────────────────────────────────────────────

def test_settings_save_button_is_always_reachable(app):
    """The theme cards made the General tab taller than the dialog and cut
    the Save button off; the tab scrolls now instead."""
    from src.gui.tabs.tab_settings import SettingsDialog
    root, _window = app
    dialog = SettingsDialog(root)
    try:
        for size in ("1060x760", "920x660"):
            dialog.geometry(size)
            pump(root, 0.4)
            panel = next(w for w in _all_widgets(dialog) if hasattr(w, "general_scroll"))
            area = panel.general_scroll
            save = next(b for b in buttons_under(area.body) if b.cget("text") == _("settings_save_btn"))
            bottom = save.winfo_rooty() + save.winfo_height()
            visible_bottom = area.canvas.winfo_rooty() + area.canvas.winfo_height()
            assert bottom <= visible_bottom or area.is_scrolling, size
            area.see(save)
            pump(root, 0.1)
            assert save.winfo_rooty() + save.winfo_height() <= visible_bottom + 1, size
    finally:
        dialog.destroy()


def test_focus_ring_only_for_keyboard_focus(app):
    root, window = app
    window.show_page("compress")
    button = window.get_active_tab().input_button
    window.focus_visible.keyboard = True
    button.focus_force()
    pump(root)
    assert button.instate(["user1"])
    root.focus_force()
    pump(root)
    assert not button.instate(["user1"])
    window.focus_visible.keyboard = False
    button.focus_force()
    pump(root)
    assert not button.instate(["user1"])


# ── Rounded corners match the surface below them ────────────────────────────

@pytest.mark.parametrize("page", PAGES)
def test_button_corners_match_their_surface(app, page):
    """Rounded button images show the style's background in their corners;
    a button on the wrong surface gets visible light or dark corners."""
    root, window = app
    window.show_page(page)
    pump(root)
    containers = [window.workspaces[page].frame, window.sidebar, window.command_bar]
    wrong = []
    for container in containers:
        for button in buttons_under(container):
            if not button.winfo_ismapped():
                continue
            mine = surface_colour(button)
            under = surface_colour(button.master)
            if mine != under:
                wrong.append(f"{button.cget('text')!r} ({button.cget('style')}): {mine} on {under}")
    assert wrong == []


# ── Themes ──────────────────────────────────────────────────────────────────

COLOUR_OPTIONS = ("background", "foreground", "highlightbackground", "highlightcolor",
                  "selectbackground", "selectforeground", "insertbackground",
                  "disabledforeground", "activebackground", "activeforeground")


@pytest.fixture
def restore_light_theme(tk_root):
    yield
    from src.gui import styles
    styles.apply_theme("paper")
    pump(tk_root)


def _all_widgets(widget):
    yield widget
    for child in widget.winfo_children():
        yield from _all_widgets(child)


def _hex(pixel):
    return "#%02X%02X%02X" % tuple(pixel[:3])


def _stale_colours(root, old, new):
    """Everything on screen still in a colour only the old theme uses:
    classic widget options, canvas drawings and fixed-colour icons."""
    from src.gui import styles
    only_old = ({c.upper() for c in old.color_tokens().values()}
                - {c.upper() for c in new.color_tokens().values()})
    bank = styles.image_bank()
    icons = {str(photo): key for key, photo in bank._photos.items() if key[0] == "icon"}
    stale = []
    for widget in _all_widgets(root):
        if not isinstance(widget, ttk.Widget):
            for option in COLOUR_OPTIONS:
                try:
                    value = str(widget.cget(option)).upper()
                except (tk.TclError, ValueError):
                    continue
                if value in only_old:
                    stale.append(f"{widget} -{option} {value}")
        if isinstance(widget, tk.Canvas):
            for item in widget.find_all():
                for option in ("fill", "outline"):
                    try:
                        value = str(widget.itemcget(item, option)).upper()
                    except tk.TclError:
                        continue
                    if value in only_old:
                        stale.append(f"{widget} item {widget.type(item)} -{option} {value}")
        try:
            images = widget.cget("image")
        except tk.TclError:
            continue
        for name in (images if isinstance(images, tuple) else (images,)):
            key = icons.get(str(name))
            if key and not bank.is_live(name) and str(key[3]).upper() in only_old:
                stale.append(f"{widget} icon {key}")
    return stale


def test_switching_theme_repaints_every_screen_without_a_restart(app, restore_light_theme, tmp_path):
    from src.gui import styles
    from src.gui.tabs.tab_settings import SettingsDialog
    from src.gui.theme import get_theme
    root, window = app
    paper, night = get_theme("paper"), get_theme("night")

    # Draw every page, a PDF in the preview, and open the dialogs, so all of
    # them have something on screen to repaint.
    pdf = make_pdf(tmp_path / "theme.pdf", pages=2)
    window.set_preview_file(pdf)
    for page in PAGES:
        window.show_page(page)
        pump(root, 0.1)
    window.show_page("compress")
    window._show_assistant_reply("Merhaba")
    before = set(root.winfo_children())
    window.preview_panel.open_viewer()
    dialog = SettingsDialog(root)
    pump(root, 0.3)
    viewer = next(w for w in root.winfo_children() if w not in before and w is not dialog)

    assert styles.apply_theme("night") is True
    pump(root, 0.2)
    assert ttk.Style(root).theme_use() == "aura-night"
    assert root.cget("bg").upper() == night.palette.canvas
    assert dialog.cget("bg").upper() == night.palette.canvas
    assert viewer.cget("bg").upper() == night.palette.stage
    assert _stale_colours(root, paper, night) == []
    # The preview stage is redrawn in the new well colour.
    stage = window.preview_panel._stage_photo
    assert _hex(stage._PhotoImage__photo.get(stage.width() // 2, 4)) == night.palette.sunken

    assert styles.apply_theme("night") is False          # already there: nothing to do
    assert styles.apply_theme("paper") is True
    pump(root, 0.2)
    assert ttk.Style(root).theme_use() == "aura-paper"
    assert _stale_colours(root, night, paper) == []

    viewer.destroy()
    dialog.destroy()
    window.hide_assistant_reply()
    window.set_preview_file(None)


@pytest.mark.parametrize("page", PAGES)
def test_button_corners_match_their_surface_in_the_dark_theme(app, restore_light_theme, page):
    from src.gui import styles
    styles.apply_theme("night")
    test_button_corners_match_their_surface(app, page)


def test_icons_follow_the_theme_in_place(app, restore_light_theme):
    """An icon drawn in P.text is the same PhotoImage after the switch, with
    new pixels, so the buttons showing it need no update."""
    from src.gui import styles
    from src.gui.theme import get_theme
    from src.gui.theme.images import Icons
    photo = styles.icon(Icons.ADD, 16, styles.P.text)
    tk_photo = photo._PhotoImage__photo

    def solid_pixels():
        return {_hex(tk_photo.get(x, y)) for x in range(photo.width()) for y in range(photo.height())
                if not tk_photo.transparency_get(x, y)}

    assert get_theme("paper").palette.text in solid_pixels()
    styles.apply_theme("night")
    assert styles.icon(Icons.ADD, 16, styles.P.text) is photo
    after = solid_pixels()
    assert get_theme("night").palette.text in after
    assert get_theme("paper").palette.text not in after


def test_new_windows_get_the_current_theme(app, restore_light_theme):
    from src.gui import styles
    from src.gui.theme import get_theme
    from src.gui.tabs.tab_settings import SettingsDialog
    root, _window = app
    styles.apply_theme("night")
    dialog = SettingsDialog(root)
    pump(root, 0.2)
    try:
        assert dialog.cget("bg").upper() == get_theme("night").palette.canvas
        assert _stale_colours(dialog, get_theme("paper"), get_theme("night")) == []
    finally:
        dialog.destroy()


def test_theme_cards_apply_and_save_the_choice(settings_panel, restore_light_theme, monkeypatch):
    from src.core.config_manager import cfg
    from src.gui import styles
    from src.gui import theme as theme_module
    monkeypatch.setitem(cfg.config, "theme", "paper")
    settings_panel._sync_theme_buttons()
    cards = settings_panel.theme_buttons
    assert list(cards) == ["paper", "night", "system"]
    assert [k for k, b in cards.items() if b.instate(["selected"])] == ["paper"]
    assert [b.cget("text") for b in cards.values()] == [_("settings_theme_light"), _("settings_theme_dark"),
                                                         _("settings_theme_system")]

    cards["night"].invoke()
    assert cfg.get("theme") == "night"
    assert styles.THEME.name == "night"
    assert [k for k, b in cards.items() if b.instate(["selected"])] == ["night"]

    # "System" follows Windows: light here, dark after Windows switches.
    windows_dark = [False]
    monkeypatch.setattr(theme_module, "system_prefers_dark", lambda: windows_dark[0])
    cards["system"].invoke()
    assert cfg.get("theme") == "system"
    assert styles.THEME.name == "paper"
    windows_dark[0] = True
    assert styles.apply_preference() is True
    assert styles.THEME.name == "night"


def test_follow_system_theme_switches_when_windows_does(tk_root, restore_light_theme, monkeypatch):
    from src.core.config_manager import cfg
    from src.gui import styles
    from src.gui import theme as theme_module
    monkeypatch.setitem(cfg.config, "theme", "system")
    monkeypatch.setattr(theme_module, "system_prefers_dark", lambda: True)
    styles.follow_system_theme(tk_root, interval_ms=20)
    assert wait_for(tk_root, lambda: styles.THEME.name == "night", timeout=2)
    # A fixed choice is left alone even when Windows is dark.
    monkeypatch.setitem(cfg.config, "theme", "paper")
    styles.apply_theme("paper")
    pump(tk_root, 0.1)
    assert styles.THEME.name == "paper"


def test_saving_settings_keeps_the_theme_choice(settings_panel, restore_light_theme, monkeypatch):
    """The theme applies on click; Save must neither undo nor re-apply it."""
    from src.core.config_manager import cfg
    monkeypatch.setitem(cfg.config, "theme", "paper")
    settings_panel.theme_buttons["night"].invoke()
    monkeypatch.setattr("tkinter.messagebox.askyesno", lambda *a, **k: False)
    settings_panel.save_settings()
    assert cfg.get("theme") == "night"


# ── Resizing ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("size", ["1100x720", "1280x800", "1920x1040"])
def test_every_page_fits_and_scrolls_at_each_size(app, size):
    root, window = app
    root.geometry(size)
    pump(root, 0.15)
    for page in PAGES:
        window.show_page(page)
        pump(root, 0.35)
        frame = window.workspaces[page].frame
        assert frame.winfo_width() <= window.content.winfo_width() + 2, f"{page} at {size}"
        # The primary action is reachable: visible, or inside a scroll area.
        tab = window.get_active_tab()
        footer = tab.footer
        # The scroll area settles over a few idle passes after a resize, so
        # wait for it rather than checking at a fixed moment (flaky on CI).
        reachable = wait_for(root, lambda: footer.action_button.winfo_ismapped()
                             or _inside_scrolling_area(footer), timeout=3.0)
        assert reachable, f"{page} at {size}"
    window.show_page("scanner")
    pump(root, 0.1)
    right = window.workspaces["scanner"].instance.preview_canvas.master
    assert right.winfo_width() >= 270, f"scanner preview squeezed at {size}"
    root.geometry("1480x920")
    pump(root, 0.1)


def _inside_scrolling_area(widget):
    from src.gui.widgets import ScrollArea
    node = widget
    while node is not None:
        if isinstance(node, ScrollArea):
            return node.is_scrolling
        node = node.master
    return False


def test_scroll_area_shows_a_scrollbar_only_when_needed(tk_root):
    from src.gui.widgets import ScrollArea
    top = tk.Toplevel(tk_root)
    top.geometry("400x300")
    area = ScrollArea(top)
    area.pack(fill="both", expand=True)
    block = ttk.Frame(area.body, height=100, width=100)
    block.pack()
    assert wait_for(tk_root, lambda: not area.is_scrolling and area.canvas.winfo_height() > 200, timeout=3)
    block.configure(height=900)
    assert wait_for(tk_root, lambda: area.is_scrolling, timeout=3)
    assert wait_for(tk_root, lambda: area.scrollbar.winfo_ismapped(), timeout=3)
    block.configure(height=50)
    assert wait_for(tk_root, lambda: not area.is_scrolling, timeout=3)
    assert wait_for(tk_root, lambda: not area.scrollbar.winfo_ismapped(), timeout=3)
    top.destroy()


def test_segmented_control_calls_back_once_per_change(tk_root):
    from src.gui.widgets import SegmentedControl
    top = tk.Toplevel(tk_root)
    var = tk.StringVar(value="A")
    calls = []
    seg = SegmentedControl(top, var, ["A", "B", "C"], command=lambda: calls.append(var.get()))
    seg.pack()
    pump(tk_root)
    seg.buttons["B"].invoke()
    seg.buttons["B"].invoke()          # same option again: no second callback
    seg.buttons["C"].invoke()
    assert calls == ["B", "C"]
    assert [v for v, b in seg.buttons.items() if b.instate(["selected"])] == ["C"]
    var.set("A")                        # set from code: the control follows
    pump(tk_root)
    assert seg.buttons["A"].instate(["selected"])
    top.destroy()


# ── Regressions found while testing the redesign ────────────────────────────

def test_scanner_takes_photos_and_its_tools_work(app, tmp_path, monkeypatch):
    """Adding the first photos raised NameError (`_` instead of `tr`) while
    suggesting the output name, so Add Photo never finished."""
    from PIL import Image, ImageDraw
    root, window = app
    paths = []
    for i in range(2):
        img = Image.new("RGB", (600, 800), (90, 70, 55))
        ImageDraw.Draw(img).polygon([(100, 90), (500, 120), (520, 700), (80, 680)], fill=(235, 232, 225))
        path = tmp_path / f"photo{i}.jpg"
        img.save(path)
        paths.append(str(path))

    window.show_page("scanner")
    tab = window.get_active_tab()
    tab.handle_external_drop_many(paths)
    assert wait_for(root, lambda: len(tab.pages) == 2 and not tab._detecting_corners, timeout=20)
    assert tab.output_var.get().endswith(_("suffix_scanned") + ".pdf")
    pump(root, 0.2)
    assert tab.canvas.find_withtag("corner_0"), "corner handles are drawn"

    page = tab.current_page
    tab.rotate_cw()
    assert wait_for(root, lambda: page.rotation == 90, timeout=5)
    tab.rotate_ccw()
    assert wait_for(root, lambda: page.rotation == 0, timeout=5)
    tab.reset_corners()
    tab.move_page(1)
    pump(root, 0.1)
    assert tab.pages[1] is page

    # Clearing asks for confirmation; answer yes without a dialog.
    monkeypatch.setattr("tkinter.messagebox.askyesno", lambda *a, **k: True)
    tab.clear_all_pages()
    assert wait_for(root, lambda: not tab.pages, timeout=3)


def test_batch_shows_the_error_of_a_failed_run(app, tmp_path, monkeypatch):
    """The error callback read `exc` after Python had unbound it, so a failed
    batch raised NameError instead of saying what went wrong."""
    import threading
    import src.gui.tabs.tab_batch as tab_batch
    root, window = app

    def broken(*_args, **_kwargs):
        raise RuntimeError("disk full")

    monkeypatch.setattr(tab_batch, "batch_compress_dir", broken)
    window.show_page("batch")
    tab = window.get_active_tab()
    tab.footer.start_busy()
    options = {"quality": "screen", "convert_mode": "pdf2img", "rename_rule": "x"}
    threading.Thread(target=tab._run_job,
                     args=(_("batch_compress"), str(tmp_path), str(tmp_path), options),
                     daemon=True).start()
    assert wait_for(root, lambda: tab.feedback.tone == "danger", timeout=5)
    assert tab.feedback.message_var.get() == "disk full"


# ── Language setting ────────────────────────────────────────────────────────

@pytest.fixture
def settings_panel(tk_root):
    from src.gui.tabs.tab_settings import SettingsPanel
    top = tk.Toplevel(tk_root)
    panel = SettingsPanel(top)
    panel.pack(fill="both", expand=True)
    pump(tk_root, 0.1)
    yield panel
    top.destroy()


def _language_combo(panel):
    def walk(widget):
        for child in widget.winfo_children():
            if isinstance(child, ttk.Combobox) and str(child.cget("textvariable")) == str(panel.lang_var):
                return child
            found = walk(child)
            if found:
                return found
    return walk(panel)


def test_language_picker_shows_names_and_saves_the_code(settings_panel, monkeypatch, tk_root):
    """It offered the raw codes "tr"/"en", and a new language silently did
    nothing because the window only hides to the tray on close."""
    from src.core.config_manager import cfg
    combo = _language_combo(settings_panel)
    from src.core.lang_manager import LANGUAGES
    assert tuple(combo.cget("values")) == tuple(LANGUAGES.values())
    assert combo.get() == "Türkçe"

    monkeypatch.setattr("tkinter.messagebox.askyesno", lambda *a, **k: False)
    combo.set("English")
    settings_panel.save_settings()
    assert cfg.get("language") == "en"
    assert settings_panel.feedback.message_var.get() == _("settings_saved_restart_later")

    combo.set("日本語")
    settings_panel.save_settings()
    assert cfg.get("language") == "ja"


def test_confirmed_language_change_restarts_the_app(settings_panel, monkeypatch, tk_root):
    calls = []
    monkeypatch.setattr(tk_root, "pdf_aura_restart", lambda: calls.append("restart"), raising=False)
    monkeypatch.setattr("tkinter.messagebox.askyesno", lambda *a, **k: True)
    settings_panel.lang_var.set("English")
    settings_panel.save_settings()
    assert calls == ["restart"]


def test_saving_without_a_language_change_does_not_ask(settings_panel, monkeypatch):
    def fail(*_a, **_k):
        raise AssertionError("asked to restart although the language did not change")
    monkeypatch.setattr("tkinter.messagebox.askyesno", fail)
    settings_panel.save_settings()
    assert settings_panel.feedback.message_var.get() == _("settings_saved")


def test_restart_starts_a_new_copy_then_quits(app, monkeypatch):
    root, window = app
    started, quits = [], []
    import src.gui.main_window as main_window

    class FakePopen:
        def __init__(self, command, **kwargs):
            started.append((command, kwargs.get("cwd")))

    monkeypatch.setattr(main_window.subprocess, "Popen", FakePopen)
    monkeypatch.setattr(window, "quit_window", lambda *a: quits.append(a))
    assert window.restart() is None
    (command, cwd), = started
    assert command[-1].endswith("main.py") and os.path.isfile(command[-1])
    assert os.path.isdir(cwd)
    assert quits, "the old copy must close"


def test_a_failed_restart_keeps_the_app_open(app, monkeypatch):
    root, window = app
    import src.gui.main_window as main_window

    def broken(*_a, **_k):
        raise OSError("no python")

    quits = []
    monkeypatch.setattr(main_window.subprocess, "Popen", broken)
    monkeypatch.setattr(window, "quit_window", lambda *a: quits.append(a))
    assert window.restart() == "no python"
    assert quits == []
