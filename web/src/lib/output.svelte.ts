// A tool's output path: suggested by Python (src.app.tools.suggest_output,
// which honours the default folder from Settings) until the user picks or
// types one; from then on it stays theirs.
import { api } from "./bridge";

export class OutputPath {
  value = $state("");
  /** Picked in a save dialog, which has already asked about replacing it. */
  picked = $state(false);
  /** Typed in by hand: no longer follows the input, but still asked about. */
  edited = $state(false);

  /** The save dialog's file type (bridge.FILE_TYPES): "pdf", "text", "docx"... */
  constructor(private tool: string, public kind = "pdf") {}

  get follows() {
    return !this.picked && !this.edited;
  }

  /** Ask before replacing only what the app chose or the user typed. */
  get ask() {
    return !this.picked;
  }

  async suggest(source: string, mode?: string | null, start?: number | null, end?: number | null) {
    if (!this.follows) return;
    this.value = source ? await api().suggest_output(this.tool, source, mode ?? null, start ?? null, end ?? null) : "";
  }

  async browse(source = "", mode?: string | null, start?: number | null, end?: number | null) {
    const suggested = this.value ||
      (source ? await api().suggest_output(this.tool, source, mode ?? null, start ?? null, end ?? null) : "");
    const path = await api().pick_save(this.kind, suggested);
    if (path) {
      this.value = path;
      this.picked = true;
    }
  }

  /** For a folder output (PDF -> Images). */
  async browseFolder() {
    const folder = await api().pick_folder(this.value);
    if (folder) {
      this.value = folder.path;
      this.picked = true;
    }
  }

  typed() {
    this.edited = true;
  }

  reset() {
    this.value = "";
    this.picked = false;
    this.edited = false;
  }
}

/** "{count} pages" for a PDF, or what went wrong reading it. */
export async function pageCount(path: string): Promise<{ pages?: number; error?: string }> {
  const doc = await api().document(path);
  if (doc.error) return { error: doc.error === "not-a-pdf" ? "" : doc.error };
  return { pages: doc.pages ?? 0 };
}
