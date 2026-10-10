"""#25 layer 5: every page, in all 14 languages, at the smallest window and
the usual one -- nothing may spill out of the window or out of its card,
and no text may be cut off without an ellipsis saying so.

    python -m pytest -m e2e tests/e2e/test_layout.py

Pixel-by-pixel screenshot baselines were left out on purpose: Windows'
font rendering differs between a desktop and the CI runner, so they would
fail without a change. These checks look at the layout itself instead.
With PDFAURA_SHOTS set to a folder, screenshots of every page in Turkish,
English and Arabic, light and dark, are saved there for a person to look
at (ci.yml uploads them).
"""
import os

import pytest

from src.core.lang_manager import LANGUAGES
from test_web_window import Window

pytestmark = pytest.mark.e2e

# The usual window, the smallest one the app allows (1100 x 720 outside,
# window.py _min_size), and a small or scaled screen that allows less.
SIZES = [(1480, 920), (1086, 681), (960, 640)]
PAGES = ["compress", "organize", "scanner", "convert", "security", "advanced", "batch", "settings"]

# Problems on the visible page, each named by where it is.
CHECK = r"""
(() => {
  const problems = [];
  const name = (el) => {
    const text = (el.innerText || el.value || el.getAttribute('aria-label') || '').trim().slice(0, 40);
    return `${el.tagName.toLowerCase()}${el.id ? '#' + el.id : ''}.${[...el.classList].join('.')} "${text}"`;
  };
  const shown = (el) => el.getClientRects().length && !el.closest('[hidden]');
  if (document.documentElement.scrollWidth > innerWidth + 1) problems.push('the window scrolls sideways');
  for (const el of document.querySelectorAll('.shell *')) {
    if (!shown(el)) continue;
    const style = getComputedStyle(el);
    const hides = ['hidden', 'clip'].includes(style.overflowX);
    // Text cut off with nothing to show it: a box that hides what does not
    // fit, narrower than its content, without an ellipsis.
    if (hides && el.scrollWidth > el.clientWidth + 1 && style.textOverflow !== 'ellipsis'
        && el.matches(':not(img, svg, canvas, video)') && el.innerText && el.innerText.trim())
      problems.push('cut off: ' + name(el));
  }
  for (const el of document.querySelectorAll('.shell button, .shell input, .shell select, .shell .field-label')) {
    if (!shown(el)) continue;
    const box = el.closest('.card, .panel-card, .segmented');
    if (!box || box === el) continue;
    const a = el.getBoundingClientRect(), b = box.getBoundingClientRect();
    if (a.right > b.right + 1 || a.left < b.left - 1) problems.push('outside its card: ' + name(el));
  }
  return problems;
})()
"""


@pytest.fixture(scope="module")
def window(tmp_path_factory):
    opened = Window(str(tmp_path_factory.mktemp("layout") / "appdata"))
    yield opened
    opened.close()


def show(window, page):
    if page == "settings":
        window.page.keyboard.press("Control+,")
        window.wait("!!document.querySelector('#settings-language')")
    else:
        window.page.keyboard.press("Escape")
        window.page.keyboard.press(f"Control+{PAGES.index(page) + 1}")
        window.wait(f"!document.querySelector('#settings-language') && "
                    f"!!document.querySelector('section.page:not([hidden])')")
    window.page.wait_for_timeout(120)


def set_language(window, code):
    show(window, "settings")
    window.page.select_option("#settings-language", code)
    window.wait(f"document.documentElement.lang === '{code}'")


@pytest.mark.parametrize("language", sorted(LANGUAGES))
def test_nothing_spills_or_is_cut_off(window, language):
    set_language(window, language)
    problems = []
    for width, height in SIZES:
        window.page.set_viewport_size({"width": width, "height": height})
        for page in PAGES:
            show(window, page)
            problems += [f"{width}x{height} {page}: {p}" for p in window.page.evaluate(CHECK)]
    window.page.set_viewport_size({"width": 1480, "height": 920})
    assert problems == [], "\n".join(problems)


@pytest.mark.skipif(not os.environ.get("PDFAURA_SHOTS"), reason="set PDFAURA_SHOTS to a folder to keep screenshots")
def test_screenshots_for_a_person_to_look_at(window):
    folder = os.environ["PDFAURA_SHOTS"]
    os.makedirs(folder, exist_ok=True)
    window.page.set_viewport_size({"width": 1480, "height": 920})
    for theme in (0, 1):                  # the Light and Dark cards in Settings
        show(window, "settings")
        window.page.evaluate(f"document.querySelectorAll('.theme-card')[{theme}].click()")
        for language in ("tr", "en", "ar"):
            set_language(window, language)
            for page in PAGES:
                show(window, page)
                window.page.screenshot(path=os.path.join(folder, f"{language}-{'dark' if theme else 'light'}-{page}.png"))
