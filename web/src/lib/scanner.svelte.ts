// The document scanner's pages, as src/app/scanboard.py last described
// them. Python owns the photos; every change goes there and the board's new
// state comes back (from the call, or as a "scanner" event when Python
// changed something on its own: detected corners, a restored session).
import { api } from "./bridge";
import { app } from "./app.svelte";
import type { Point, ScanMode, ScanNotice, ScanPage, ScanState } from "./types";

export const MODES: { mode: ScanMode; label: string }[] = [
  { mode: "original", label: "scanner_mode_original" },
  { mode: "clean_doc", label: "scanner_mode_clean_doc" },
  { mode: "bw", label: "scanner_mode_bw" },
  { mode: "grayscale", label: "scanner_mode_grayscale" },
  { mode: "sharp", label: "scanner_mode_sharp" },
];

// src/app/scanner.py IMAGE_EXTENSIONS: what OpenCV reads.
export const IMAGE_EXTENSIONS = [".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"];

// Pictures are asked for at fixed sizes, so a resize never fetches them
// again; the page scales them down.
const PHOTO_PX = 2000;
const THUMB_PX: Point = [360, 510];
const PREVIEW_PX: Point = [520, 740];

function url(page: ScanPage, kind: string, [w, h]: Point, key: string | number) {
  return `/scan/${app.token}/${page.uid}/${kind}?w=${w}&h=${h}&v=${key}`;
}

/** The photo as turned. Its pixels change only with the rotation. */
export function photoUrl(page: ScanPage) {
  return url(page, "photo", [PHOTO_PX, PHOTO_PX], `r${page.rotation}`);
}

/** The page straightened, as it goes into the PDF. */
export function thumbUrl(page: ScanPage) {
  return url(page, "thumb", THUMB_PX, page.version);
}

/** The straightened page in the scan style. */
export function previewUrl(page: ScanPage, mode: ScanMode) {
  return url(page, "preview", PREVIEW_PX, `${page.version}-${mode}`);
}

export class ScanBoard {
  pages = $state<ScanPage[]>([]);
  current = $state(-1);
  mode = $state<ScanMode>("clean_doc");
  output = $state("");
  busy = $state<ScanState["busy"]>(null);
  progress = $state<ScanState["progress"]>(null);
  /** Calls on their way: adding photos takes a moment per photo. */
  pending = $state(0);
  /** The strip's width the user chose; 0 fits it beside the photo. */
  strip = $state(0);
  page = $derived<ScanPage | null>(this.pages[this.current] ?? null);
  /** Detection, an export or the restore depends on the pages staying put. */
  locked = $derived(this.busy !== null);

  constructor(private onNotice: (notice: ScanNotice) => void = () => {}) {}

  apply(state: ScanState) {
    this.pages = state.pages;
    this.current = state.current;
    this.mode = state.mode;
    this.output = state.output;
    this.busy = state.busy;
    this.progress = state.progress;
    if (state.notice) this.onNotice(state.notice);
  }

  private async call(request: Promise<ScanState>) {
    this.pending += 1;
    try {
      this.apply(await request);
    } finally {
      this.pending -= 1;
    }
  }

  async open() {
    const state = await api().scanner_open();
    this.strip = state.strip;
    this.apply(state);
  }

  add(paths: string[]) {
    const photos = paths.filter((path) => IMAGE_EXTENSIONS.some((ext) => path.toLowerCase().endsWith(ext)));
    if (photos.length) return this.call(api().scanner_add(photos));
  }

  select(index: number) {
    if (index < 0 || index >= this.pages.length || index === this.current) return;
    this.current = index;
    return this.call(api().scanner_select(index));
  }

  move(page: ScanPage, index: number) {
    return this.call(api().scanner_move(page.uid, index));
  }

  remove(page: ScanPage) {
    return this.call(api().scanner_remove(page.uid));
  }

  clear() {
    return this.call(api().scanner_clear());
  }

  rename(page: ScanPage, label: string) {
    return this.call(api().scanner_rename(page.uid, label));
  }

  rotate(page: ScanPage, step: 90 | -90) {
    return this.call(api().scanner_rotate(page.uid, step));
  }

  setCorners(page: ScanPage, corners: Point[]) {
    // Shown at once; Python rounds and clamps them and sends them back.
    page.corners = corners;
    return this.call(api().scanner_corners(page.uid, corners));
  }

  reset(page: ScanPage) {
    return this.call(api().scanner_reset(page.uid));
  }

  detect(page: ScanPage) {
    return this.call(api().scanner_detect(page.uid));
  }

  setMode(mode: ScanMode) {
    this.mode = mode;
    return this.call(api().scanner_mode(mode));
  }

  setOutput(path: string) {
    this.output = path;
    return this.call(api().scanner_output(path));
  }

  saveStrip(width: number) {
    this.strip = width;
    void api().scanner_strip(width);
  }
}
