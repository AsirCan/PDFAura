// The window's shared state: which page is open, the theme, recent files,
// the preview, the assistant. Components read it; actions below change it.
import { api, on } from "./bridge";
import { language } from "./i18n.svelte";
import type { AssistantState, Boot, FileInfo, Settings, ThemeName, ThemePreference } from "./types";
import type { IconName } from "./generated/icons";

export const PAGES = ["compress", "organize", "scanner", "convert", "security", "advanced", "batch"] as const;
export type Page = (typeof PAGES)[number];

// Sidebar order (Ctrl+1 … Ctrl+7 follow it), as NAV_ITEMS in main_window.py.
export const NAV: { page: Page; icon: IconName; label: string }[] = [
  { page: "compress", icon: "COMPRESS", label: "txt_compress" },
  { page: "organize", icon: "ORGANIZE", label: "txt_edit" },
  { page: "scanner", icon: "SCAN", label: "txt_scan" },
  { page: "convert", icon: "CONVERT", label: "txt_convert" },
  { page: "security", icon: "SECURITY", label: "txt_security" },
  { page: "advanced", icon: "ADVANCED", label: "txt_advanced" },
  { page: "batch", icon: "BATCH", label: "txt_batch" },
];

/** Pages that bring their own preview (the scanner) hide the shared one. */
export const OWN_PREVIEW: readonly Page[] = ["scanner"];

type DropHandler = (files: FileInfo[]) => void;

class AppState {
  page = $state<Page>("compress");
  settingsOpen = $state(false);
  theme = $state<ThemePreference>("system");
  systemDark = $state(false);
  shown = $derived<ThemeName>(this.theme === "system" ? (this.systemDark ? "night" : "paper") : this.theme);
  settings = $state<Settings>({ close_to_tray: true, sound_enabled: true, default_output_dir: "" });
  recent = $state<FileInfo[]>([]);
  languages = $state<[string, string][]>([]);
  version = $state("");
  token = $state("");
  /** The PDF in the preview panel. */
  preview = $state<string | null>(null);
  /** The PDF open in the full-window viewer. */
  viewer = $state<string | null>(null);
  assistant = $state<AssistantState>("idle");
  assistantHeard = $state("");
  reply = $state<string | null>(null);
  ready = $state(false);
  /** What each page does with files dropped on the window. */
  private dropTargets = new Map<Page, DropHandler>();

  load(boot: Boot) {
    language.apply(boot);
    this.theme = boot.theme;
    this.settings = boot.settings;
    this.recent = boot.recent;
    this.languages = boot.languages;
    this.version = boot.version;
    this.token = boot.token;
    this.ready = true;
  }

  /** Register what a page does with dropped files; returns the undo. */
  acceptDrops(page: Page, handler: DropHandler): () => void {
    this.dropTargets.set(page, handler);
    return () => {
      if (this.dropTargets.get(page) === handler) this.dropTargets.delete(page);
    };
  }

  /** Files dropped on the window go to the page that is showing. */
  drop(files: FileInfo[]) {
    if (this.settingsOpen || this.viewer) return;
    this.dropTargets.get(this.page)?.(files);
  }
}

export const app = new AppState();

// ── Actions ────────────────────────────────────────────────────────────

export function showPage(page: Page) {
  app.page = page;
}

export async function setTheme(preference: ThemePreference) {
  app.theme = preference;
  await api().set_theme(preference);
}

export async function setLanguage(code: string) {
  language.apply(await api().set_language(code));
}

export async function refreshRecent() {
  app.recent = await api().recent_files();
}

export function previewFile(path: string | null) {
  app.preview = path && path.toLowerCase().endsWith(".pdf") ? path : null;
}

/** Wire the events Python sends that the window as a whole handles. */
export function listen(): () => void {
  const undo = [
    on("drop", ({ files }) => app.drop(files)),
    on("assistant", ({ state, detail }) => {
      app.assistant = state;
      app.assistantHeard = state === "heard" ? detail : "";
    }),
    on("assistant-reply", ({ text }) => {
      app.reply = text;
    }),
    on("job", (event) => {
      if (event.type === "done") void refreshRecent();
    }),
  ];
  return () => undo.forEach((stop) => stop());
}

/** Follow Windows' light/dark setting while the preference is "system". */
export function followSystemTheme(): () => void {
  const query = window.matchMedia("(prefers-color-scheme: dark)");
  app.systemDark = query.matches;
  const change = (event: MediaQueryListEvent) => {
    app.systemDark = event.matches;
  };
  query.addEventListener("change", change);
  return () => query.removeEventListener("change", change);
}
