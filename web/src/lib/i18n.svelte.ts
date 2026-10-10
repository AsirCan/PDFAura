// Every visible string comes from src/core/lang_manager.py, sent whole at
// start-up and again when the language changes, so a new language shows at
// once without a restart. The browser lays out right-to-left text itself
// (dir="rtl"); the strings carry none of Tk's direction marks.
import type { LanguagePayload } from "./types";

class Language {
  code = $state("tr");
  rtl = $state(false);
  strings = $state<Record<string, string>>({});

  apply(payload: LanguagePayload) {
    this.code = payload.language;
    this.rtl = payload.rtl;
    this.strings = payload.strings;
    const root = document.documentElement;
    root.lang = payload.language;
    root.dir = payload.rtl ? "rtl" : "ltr";
  }
}

export const language = new Language();

// Python's str.format with the one spec the strings use, "{size:.2f}".
const FIELD = /\{(\w+)(?::\.(\d+)f)?\}/g;

export function format(text: string, values: Record<string, unknown> = {}): string {
  return text.replace(FIELD, (whole, name: string, digits?: string) => {
    if (!(name in values)) return whole;
    const value = values[name];
    if (digits !== undefined && typeof value === "number") return value.toFixed(Number(digits));
    return String(value);
  });
}

/** The string for ``key`` in the current language, with {fields} filled in. */
export function t(key: string, values?: Record<string, unknown>): string {
  const text = language.strings[key] ?? key;
  return values ? format(text, values) : text;
}
