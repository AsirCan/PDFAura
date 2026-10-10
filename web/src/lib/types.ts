// What Python sends and takes: mirrors src/app/bridge.py. Keep the two in
// step; tests/test_bridge_contract.py compares the method names.

export type ThemePreference = "system" | "paper" | "night";
export type ThemeName = "paper" | "night";
export type Tone = "success" | "warning" | "error" | "info";

export interface FileInfo {
  path: string;
  name: string;
  folder: string;
  ext: string;
  kind: "pdf" | "image" | "word" | "powerpoint" | "excel" | "text" | "folder" | "other";
  size: number;
  exists: boolean;
  is_dir: boolean;
}

export interface Settings {
  close_to_tray: boolean;
  sound_enabled: boolean;
  default_output_dir: string;
}

export interface LanguagePayload {
  language: string;
  rtl: boolean;
  strings: Record<string, string>;
}

export interface Boot extends LanguagePayload {
  languages: [string, string][];
  theme: ThemePreference;
  settings: Settings;
  recent: FileInfo[];
  token: string;
  version: string;
}

export interface Outcome {
  title: string;
  message: string;
  output: string | null;
  tone: Tone;
  details: Record<string, unknown>;
}

export interface Started {
  job?: number;
  busy?: string;
  cancellable?: boolean;
  problem?: string;
}

export interface PdfDocument extends FileInfo {
  error?: string;
  id?: string;
  pages?: number;
  width?: number;
  height?: number;
  encrypted?: boolean;
  version?: number;
  base?: string;
}

export interface ModelRow {
  id: string;
  name: string;
  category: string;
  size: string;
  hardware: string;
  installed: boolean;
  description: string;
  message: string;
  path: string;
  license: string;
  notes: string;
  downloadable: boolean;
  source_url: string;
}

export interface ModelList {
  root: string;
  rows: ModelRow[];
}

export type Params = Record<string, unknown>;

// The document scanner (src/app/scanboard.py). Corners are photo pixels,
// clockwise from the top-left, in the photo as it is turned.
export type Point = [number, number];
export type ScanMode = "original" | "clean_doc" | "bw" | "grayscale" | "sharp";

export interface ScanPage {
  uid: string;
  label: string;
  name: string;
  width: number;
  height: number;
  rotation: number;
  corners: Point[];
  /** Changes whenever the page's straightened picture would. */
  version: number;
}

export interface ScanNotice {
  tone: Tone;
  title: string;
  message: string;
}

export interface ScanState {
  pages: ScanPage[];
  current: number;
  mode: ScanMode;
  output: string;
  busy: "restoring" | "exporting" | "detecting" | null;
  notice: ScanNotice | null;
  progress: { current: number; total: number } | null;
}

export interface ScanOpen extends ScanState {
  /** The strip's width the user chose; 0 fits it beside the photo. */
  strip: number;
}

export interface Metadata {
  title: string;
  author: string;
  subject: string;
  creator: string;
}

export interface Api {
  boot(): Promise<Boot>;
  set_language(code: string): Promise<LanguagePayload>;
  set_theme(preference: ThemePreference): Promise<ThemePreference>;
  theme_shown(name: ThemeName): Promise<void>;
  settings(): Promise<Settings>;
  save_settings(values: Settings): Promise<Settings>;
  recent_files(): Promise<FileInfo[]>;
  clear_recent(): Promise<FileInfo[]>;
  file_info(paths: string[]): Promise<FileInfo[]>;
  pick_files(kind?: string, multiple?: boolean): Promise<FileInfo[]>;
  pick_folder(start?: string): Promise<FileInfo | null>;
  pick_save(kind?: string, suggested?: string): Promise<string | null>;
  open_path(path: string): Promise<boolean>;
  reveal_path(path: string): Promise<boolean>;
  check(tool: string, params: Params): Promise<string | null>;
  existing_target(tool: string, params: Params): Promise<string | null>;
  suggest_output(tool: string, source: string, mode?: string | null, start?: number | null,
                 end?: number | null): Promise<string>;
  start(tool: string, params: Params): Promise<Started>;
  cancel(job: number): Promise<void>;
  document(path: string): Promise<PdfDocument>;
  tesseract_available(): Promise<boolean>;
  install_tesseract(): Promise<void>;
  read_metadata(path: string): Promise<Metadata & { error?: string }>;
  scanner_open(): Promise<ScanOpen>;
  scanner_add(paths: string[]): Promise<ScanState>;
  scanner_remove(uid: string): Promise<ScanState>;
  scanner_clear(): Promise<ScanState>;
  scanner_select(index: number): Promise<ScanState>;
  scanner_move(uid: string, index: number): Promise<ScanState>;
  scanner_rename(uid: string, label: string): Promise<ScanState>;
  scanner_rotate(uid: string, step: 90 | -90): Promise<ScanState>;
  scanner_corners(uid: string, corners: Point[]): Promise<ScanState>;
  scanner_reset(uid: string): Promise<ScanState>;
  scanner_detect(uid: string): Promise<ScanState>;
  scanner_mode(mode: ScanMode): Promise<ScanState>;
  scanner_output(path: string): Promise<ScanState>;
  scanner_strip(width: number): Promise<number>;
  scanner_export(): Promise<Started>;
  assistant_submit(text: string): Promise<boolean>;
  assistant_press(): Promise<void>;
  assistant_release(): Promise<void>;
  models(root?: string | null): Promise<ModelList>;
  models_save_root(root: string): Promise<ModelList>;
  models_pick_path(id: string): Promise<ModelList | null>;
  models_download(id: string): Promise<{ job?: number; source_url?: string }>;
  models_test(id: string): Promise<void>;
  quit(): Promise<void>;
}

// Events Python sends unasked (src/app/events.py).
export type JobEvent =
  | { id: number; type: "progress"; current: number; total: number; message: string }
  | { id: number; type: "done"; outcome: Outcome }
  | { id: number; type: "failed"; title: string; message: string }
  | { id: number; type: "cancelled" };

export type AssistantState = "idle" | "loading" | "listening" | "processing" | "heard" | "missing";

export interface Events {
  job: JobEvent;
  assistant: { state: AssistantState; detail: string };
  "assistant-reply": { text: string };
  drop: { files: FileInfo[] };
  "model-test": { id: string; ok: boolean; message: string };
  tesseract: { ok: boolean; message: string };
  scanner: ScanState;
}
