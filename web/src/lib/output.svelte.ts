// A tool's output path: suggested by Python (src.app.tools.suggest_output,
// which honours the default folder from Settings) until the user picks or
// types one; from then on it stays theirs.
import { api } from "./bridge";

export class OutputPath {
  value = $state("");
  /** Picked in a save dialog, for the input and mode in pickedFor. */
  picked = $state(false);
  /** Typed in by hand: no longer follows the input, but still asked about. */
  edited = $state(false);
  private pickedFor: { source: string; mode: string | null } | null = null;
  /** The save dialog asked about replacing the file; that answer covers the
   * next run only. */
  private confirmed = false;

  /** The save dialog's file type (bridge.FILE_TYPES): "pdf", "text", "docx"... */
  constructor(private tool: string, public kind = "pdf") {}

  get follows() {
    return !this.picked && !this.edited;
  }

  /** Ask before a run on ``source`` replaces the file, unless the save
   * dialog has just asked about it for this input. */
  askFor(source?: string) {
    if (!this.picked || !this.confirmed) return true;
    const pickedSource = this.pickedFor?.source ?? "";
    return source !== undefined && pickedSource !== "" && pickedSource !== source.trim();
  }

  /** Follow a new input or mode. A path picked for another input or mode is
   * dropped: it kept B's result going to A's file, and the OCR text over the
   * PDF picked for the signature, without a question (#28). */
  async suggest(source: string, mode?: string | null, start?: number | null, end?: number | null) {
    if (this.pickedFor) {
      // Picked before an input was chosen: it is this input's.
      if (!this.pickedFor.source) this.pickedFor.source = source.trim();
      if (this.pickedFor.source !== source.trim() || this.pickedFor.mode !== (mode ?? null)) this.unpick();
    }
    if (!this.follows) return;
    this.value = source ? await api().suggest_output(this.tool, source, mode ?? null, start ?? null, end ?? null) : "";
  }

  async browse(source = "", mode?: string | null, start?: number | null, end?: number | null) {
    const suggested = this.value ||
      (source ? await api().suggest_output(this.tool, source, mode ?? null, start ?? null, end ?? null) : "");
    const path = await api().pick_save(this.kind, suggested);
    if (path) this.pick(path, source, mode);
  }

  /** For a folder output (PDF -> Images). The folder dialog says nothing
   * about the files in it, so a run still asks before replacing them. */
  async browseFolder(source = "", mode?: string | null) {
    const folder = await api().pick_folder(this.value);
    if (folder) this.pick(folder.path, source, mode, false);
  }

  typed() {
    this.edited = true;
    // The dialog asked about the path it gave, not this one.
    this.unpick();
  }

  /** A run is writing to the path. The save dialog's answer was for that
   * run: the next one asks again if the file is there by then. */
  used() {
    this.confirmed = false;
  }

  private pick(path: string, source: string, mode?: string | null, confirmed = true) {
    this.value = path;
    this.picked = true;
    this.confirmed = confirmed;
    this.edited = false;
    this.pickedFor = { source: source.trim(), mode: mode ?? null };
  }

  private unpick() {
    this.picked = false;
    this.confirmed = false;
    this.pickedFor = null;
  }
}

/** "{count} pages" for a PDF, or what went wrong reading it. */
export async function pageCount(path: string): Promise<{ pages?: number; error?: string }> {
  const doc = await api().document(path);
  if (doc.error) return { error: doc.error === "not-a-pdf" ? "" : doc.error };
  return { pages: doc.pages ?? 0 };
}
