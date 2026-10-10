// A stand-in for src/app/bridge.py: for component tests and for working on
// the page in a plain browser (npm run dev). It answers like Python would,
// without touching any file; jobs "run" on timers.
import { emit } from "./bridge";
import type { Api, Boot, FileInfo, ModelList, Params, Settings, ThemePreference } from "./types";

export interface FakeOptions {
  strings?: Record<string, string>;
  language?: string;
  /** How long a fake job takes, in ms; 0 finishes at once. */
  jobMs?: number;
  /** Return this from check() instead of null. */
  problem?: string | null;
  /** Files the next pick_files() returns. */
  picks?: string[];
}

function info(path: string): FileInfo {
  const name = path.split(/[\\/]/).pop() ?? path;
  const dot = name.lastIndexOf(".");
  const ext = dot >= 0 ? name.slice(dot).toLowerCase() : "";
  const kinds: Record<string, FileInfo["kind"]> = {
    ".pdf": "pdf", ".png": "image", ".jpg": "image", ".jpeg": "image", ".docx": "word", ".doc": "word",
    ".pptx": "powerpoint", ".xlsx": "excel", ".txt": "text",
  };
  return {
    path, name, folder: path.slice(0, path.length - name.length - 1), ext,
    kind: ext ? kinds[ext] ?? "other" : "folder", size: 1_234_567, exists: true, is_dir: !ext,
  };
}

export function createFakeBridge(options: FakeOptions = {}): Api & { calls: [string, unknown[]][] } {
  const calls: [string, unknown[]][] = [];
  let settings: Settings = { close_to_tray: true, sound_enabled: true, default_output_dir: "" };
  let theme: ThemePreference = "system";
  let recent: FileInfo[] = [];
  let jobs = 0;
  const timers = new Map<number, ReturnType<typeof setTimeout>[]>();
  const strings = options.strings ?? {};
  const record = (name: string, args: unknown[]) => calls.push([name, args]);
  const models: ModelList = {
    root: "C:\\Users\\Örnek\\AppData\\Roaming\\PDFAura\\models",
    rows: [
      { id: "scanner_u2netp", name: "Belge Kenar Modeli", category: "vision", size: "4.7 MB", hardware: "Hafif",
        installed: true, description: "", message: "", path: "", license: "", notes: "", downloadable: true,
        source_url: "" },
      { id: "speech_whisper", name: "Ses Tanıma", category: "speech", size: "~460 MB", hardware: "Standart",
        installed: false, description: "", message: "", path: "", license: "", notes: "", downloadable: false,
        source_url: "https://example.invalid" },
    ],
  };

  const bridge: Api & { calls: typeof calls } = {
    calls,
    async boot(): Promise<Boot> {
      record("boot", []);
      return {
        language: options.language ?? "tr", rtl: options.language === "ar" || options.language === "ur",
        strings, languages: [["tr", "Türkçe"], ["en", "English"], ["ar", "العربية"]], theme, settings,
        recent, token: "fake", version: "dev",
      };
    },
    async set_language(code) {
      record("set_language", [code]);
      return { language: code, rtl: code === "ar" || code === "ur", strings };
    },
    async set_theme(preference) {
      record("set_theme", [preference]);
      theme = preference;
      return theme;
    },
    async theme_shown(name) {
      record("theme_shown", [name]);
    },
    async settings() {
      return settings;
    },
    async save_settings(values) {
      record("save_settings", [values]);
      settings = { ...values };
      return settings;
    },
    async recent_files() {
      return recent;
    },
    async clear_recent() {
      record("clear_recent", []);
      recent = [];
      return recent;
    },
    async file_info(paths) {
      return paths.map(info);
    },
    async pick_files(kind = "pdf", multiple = false) {
      record("pick_files", [kind, multiple]);
      const picks = options.picks ?? ["C:\\Belgeler\\rapor.pdf"];
      return (multiple ? picks : picks.slice(0, 1)).map(info);
    },
    async pick_folder() {
      record("pick_folder", []);
      return info("C:\\Belgeler\\Çıktı");
    },
    async pick_save(kind = "pdf", suggested = "") {
      record("pick_save", [kind, suggested]);
      return suggested || "C:\\Belgeler\\cikti.pdf";
    },
    async open_path(path) {
      record("open_path", [path]);
      return true;
    },
    async reveal_path(path) {
      record("reveal_path", [path]);
      return true;
    },
    async check(tool, params) {
      record("check", [tool, params]);
      return options.problem ?? null;
    },
    async existing_target() {
      return null;
    },
    async suggest_output(tool, source, mode) {
      record("suggest_output", [tool, source, mode]);
      if (!source) return "";
      const dot = source.lastIndexOf(".");
      return `${dot > 0 ? source.slice(0, dot) : source}_${tool}${mode ? `_${mode}` : ""}.pdf`;
    },
    async start(tool: string, params: Params) {
      record("start", [tool, params]);
      if (options.problem) return { problem: options.problem };
      const id = ++jobs;
      const ms = options.jobMs ?? 600;
      const steps = [1, 2, 3].map((step) => setTimeout(() => {
        emit("job", { id, type: "progress", current: step, total: 3, message: "" });
      }, (ms * step) / 4));
      steps.push(setTimeout(() => {
        const output = String(params.output ?? "C:\\Belgeler\\cikti.pdf");
        recent = [info(output), ...recent.filter((file) => file.path !== output)].slice(0, 5);
        emit("job", { id, type: "done", outcome: { title: "Tamam", message: `${tool} bitti`, output, tone: "success",
                                                   details: {} } });
      }, ms));
      timers.set(id, steps);
      return { job: id, busy: `${tool}…`, cancellable: true };
    },
    async cancel(job) {
      record("cancel", [job]);
      for (const timer of timers.get(job) ?? []) clearTimeout(timer);
      emit("job", { id: job, type: "cancelled" });
    },
    async document(path) {
      record("document", [path]);
      const file = info(path);
      if (file.kind !== "pdf") return { ...file, error: "not-a-pdf" };
      return { ...file, id: "doc", pages: 12, width: 595, height: 842, encrypted: false, version: 1, base: "" };
    },
    async assistant_submit(text) {
      record("assistant_submit", [text]);
      emit("assistant", { state: "processing", detail: "" });
      setTimeout(() => {
        emit("assistant-reply", { text: `“${text}”` });
        emit("assistant", { state: "idle", detail: "" });
      }, options.jobMs ?? 300);
      return true;
    },
    async assistant_press() {
      record("assistant_press", []);
      emit("assistant", { state: "listening", detail: "" });
    },
    async assistant_release() {
      record("assistant_release", []);
      emit("assistant", { state: "idle", detail: "" });
    },
    async models() {
      return models;
    },
    async models_save_root(root) {
      models.root = root;
      return models;
    },
    async models_pick_path() {
      return models;
    },
    async models_download(id) {
      record("models_download", [id]);
      return { job: ++jobs };
    },
    async models_test(id) {
      record("models_test", [id]);
      setTimeout(() => emit("model-test", { id, ok: true, message: "ok" }), 0);
    },
    async quit() {
      record("quit", []);
    },
  };
  return bridge;
}
