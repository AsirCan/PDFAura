<script lang="ts">
  // Belge Tara: photos in, each straightened into one page
  // of a PDF. The pages and their photos live in Python (scanboard.py); this
  // page shows them, lets the corners be dragged without asking Python, and
  // sends each change once it is made.
  import { onDestroy, onMount } from "svelte";
  import { api, on } from "../lib/bridge";
  import { app } from "../lib/app.svelte";
  import { dialogs } from "../lib/dialog.svelte";
  import { t } from "../lib/i18n.svelte";
  import { Feedback, ToolRun } from "../lib/run.svelte";
  import { MODES, previewUrl, ScanBoard } from "../lib/scanner.svelte";
  import type { Point, ScanMode, ScanNotice } from "../lib/types";
  import FeedbackPanel from "../components/Feedback.svelte";
  import Icon from "../components/Icon.svelte";
  import ProgressFooter from "../components/ProgressFooter.svelte";
  import CornerEditor from "../components/scanner/CornerEditor.svelte";
  import PageStrip from "../components/scanner/PageStrip.svelte";

  const SASH = 10;
  const STRIP_MIN = 132;
  const EDITOR_MIN = 320;
  const FIT_MARGIN = 22;

  const feedback = new Feedback(() => t("scanner_scan_mode"), () => t("scanner_select_hint"));
  const run = new ToolRun(feedback);
  const board = new ScanBoard(notify);

  /** The output was picked in the save dialog, which asked about replacing it. */
  let picked = $state(false);
  let fullscreen = $state(false);
  let previewLoaded = $state(false);
  let workW = $state(0);
  let workH = $state(0);
  let sashDrag: { x: number; width: number; moved: boolean } | null = null;
  let dragWidth = $state<number | null>(null);

  let page = $derived(board.page);
  let locked = $derived(board.locked || run.busy);
  let working = $derived.by(() => {
    if (board.busy === "detecting") {
      return board.progress
        ? t("scanner_detecting_progress", { current: board.progress.current, total: board.progress.total })
        : t("scanner_detecting");
    }
    if (board.busy === "restoring") return t("scanner_session_restoring");
    return board.pending ? t("str_processing") : null;
  });
  let preview = $derived(page ? previewUrl(page, board.mode) : null);

  // Auto width (0): the strip takes the room a narrow, portrait photo
  // leaves beside it. A width the user dragged is kept, within the window.
  let stripWidth = $derived.by(() => {
    if (!workW) return STRIP_MIN;
    const max = Math.max(STRIP_MIN, workW - SASH - EDITOR_MIN);
    let want = dragWidth ?? board.strip;
    if (!want) {
      const aspects = board.pages.map((p) => p.width / p.height).sort((a, b) => a - b);
      if (!aspects.length) want = STRIP_MIN;
      else {
        // The median: one odd landscape page doesn't reshape a portrait document.
        const half = Math.floor(aspects.length / 2);
        const median = aspects.length % 2 ? aspects[half] : (aspects[half - 1] + aspects[half]) / 2;
        want = workW - SASH - ((workH - FIT_MARGIN) * median + FIT_MARGIN);
      }
    }
    return Math.round(Math.max(STRIP_MIN, Math.min(max, want)));
  });

  function notify(notice: ScanNotice) {
    if (run.busy) return;
    if (notice.tone === "error") feedback.error(notice.title, notice.message);
    else feedback.info(notice.title, notice.message);
  }

  $effect(() => {
    if (working && board.busy) feedback.busy(working);
  });

  $effect(() => {
    if (!board.output) picked = false;
  });

  $effect(() => {
    void preview;
    previewLoaded = false;
  });

  function refused() {
    feedback.info(() => t("scanner_crop_area"), () => t("scanner_detect_busy"));
  }

  // ── Photos in and out ──────────────────────────────────────────────
  async function addPhotos() {
    if (locked) return refused();
    const files = await api().pick_files("photo", true);
    if (files.length) await board.add(files.map((file) => file.path));
  }

  async function clearAll() {
    if (!board.pages.length || locked) return;
    const yes = await dialogs.ask({
      title: t("scanner_clear_all"), body: t("scanner_clear_all_confirm"), confirm: t("scanner_clear_all"),
      cancel: t("str_cancel"), danger: true,
    });
    if (yes) await board.clear();
  }

  // ── The current page ───────────────────────────────────────────────
  function commit(corners: Point[]) {
    if (page && !locked) void board.setCorners(page, corners);
  }

  function openFullscreen() {
    if (locked) return refused();
    if (page) fullscreen = true;
  }

  function overlayKey(event: KeyboardEvent) {
    if (event.key === "Escape") {
      event.preventDefault();
      fullscreen = false;
    }
    // The window's own shortcuts wait until the crop is closed.
    event.stopPropagation();
  }

  function focusNode(node: HTMLElement) {
    node.focus();
  }

  // ── Output and export ──────────────────────────────────────────────
  async function chooseOutput() {
    const path = await api().pick_save("pdf", board.output);
    if (path) {
      picked = true;
      await board.setOutput(path);
    }
  }

  function typedOutput(value: string) {
    picked = false;
    void board.setOutput(value.trim());
  }

  async function exportPdf() {
    if (locked) return refused();
    if (!board.pages.length) return feedback.error(() => t("str_error"), () => t("scanner_no_image"));
    const output = board.output.trim();
    if (!output) return feedback.error(() => t("str_error"), () => t("err_set_output"));
    if (!picked) {
      const [target] = await api().file_info([output]);
      if (target?.exists) {
        const replace = await dialogs.ask({
          title: t("overwrite_title"), body: t("overwrite_body", { path: output }),
          confirm: t("overwrite_replace"), cancel: t("str_cancel"), danger: true,
        });
        if (!replace) return;
      }
    }
    // Python locks the pages for the export; show it at once.
    board.busy = "exporting";
    if (!(await run.begin(() => api().scanner_export()))) board.busy = null;
  }

  // ── The strip's width ──────────────────────────────────────────────
  function sashDown(event: PointerEvent) {
    if (event.button !== 0) return;
    (event.currentTarget as Element).setPointerCapture?.(event.pointerId);
    sashDrag = { x: event.clientX, width: stripWidth, moved: false };
  }

  function sashMove(event: PointerEvent) {
    if (!sashDrag) return;
    const dx = (event.clientX - sashDrag.x) * (document.documentElement.dir === "rtl" ? -1 : 1);
    if (Math.abs(dx) >= 2) sashDrag.moved = true;
    dragWidth = Math.max(STRIP_MIN, sashDrag.width + dx);
  }

  function sashUp() {
    const drag = sashDrag;
    sashDrag = null;
    if (drag?.moved) board.saveStrip(stripWidth);
    dragWidth = null;
  }

  function sashKey(event: KeyboardEvent) {
    const forward = document.documentElement.dir === "rtl" ? -1 : 1;
    const steps: Record<string, number> = { ArrowLeft: -16 * forward, ArrowRight: 16 * forward };
    if (event.key in steps) {
      event.preventDefault();
      board.saveStrip(Math.max(STRIP_MIN, stripWidth + steps[event.key]));
    } else if (event.key === "Home" || event.key === "Enter") {
      event.preventDefault();
      board.saveStrip(0);
    }
  }

  onMount(() => {
    const stops = [
      on("scanner", (state) => board.apply(state)),
      app.acceptDrops("scanner", (files) => {
        if (fullscreen) return;
        // One batch: photos added one by one would be refused while the
        // first one's corners are still being found.
        const photos = files.filter((file) => file.kind === "image").map((file) => file.path);
        if (!photos.length) return;
        if (locked) return refused();
        void board.add(photos);
      }),
    ];
    void board.open();
    return () => stops.forEach((stop) => stop());
  });
  onDestroy(() => run.dispose());
</script>

<div class="scanner">
  <p class="hint-strip small">
    <Icon name="INFO" size={13} />
    <span>{t("hint_scanner")}</span>
  </p>
  <div class="body">
    <section class="editor-card card">
      <div class="toolbar">
        <button class="btn btn-secondary" type="button" disabled={locked} onclick={addPhotos}>
          <Icon name="ADD" size={12} /><span class="label">{t("scanner_add_photo")}</span>
        </button>
        <button class="btn btn-ghost collapse" type="button" title={t("scanner_remove_photo")}
                disabled={locked || !page} onclick={() => page && board.remove(page)}>
          <Icon name="DELETE" size={12} /><span class="label">{t("scanner_remove_photo")}</span>
        </button>
        <button class="btn btn-ghost collapse" type="button" title={t("scanner_clear_all")}
                disabled={locked || !board.pages.length} onclick={clearAll}>
          <Icon name="CLEAR" size={12} /><span class="label">{t("scanner_clear_all")}</span>
        </button>
        <span class="grow"></span>
        <button class="btn btn-ghost collapse" type="button" title={t("scanner_fullscreen_crop")}
                disabled={locked || !page} onclick={openFullscreen}>
          <Icon name="FULLSCREEN" size={12} /><span class="label">{t("scanner_fullscreen_crop")}</span>
        </button>
      </div>
      <div class="toolbar">
        <button class="btn btn-secondary btn-small" type="button" disabled={locked || !page}
                onclick={() => page && board.rotate(page, -90)}>{t("scanner_rotate_ccw")}</button>
        <button class="btn btn-secondary btn-small" type="button" disabled={locked || !page}
                onclick={() => page && board.rotate(page, 90)}>{t("scanner_rotate_cw")}</button>
        <span class="separator"></span>
        <button class="btn btn-secondary btn-small collapse" type="button" title={t("scanner_auto_detect")}
                disabled={locked || !page} onclick={() => page && board.detect(page)}>
          <Icon name="SPARK" size={12} /><span class="label">{t("scanner_auto_detect")}</span>
        </button>
        <button class="btn btn-secondary btn-small collapse" type="button" title={t("scanner_reset_corners")}
                disabled={locked || !page} onclick={() => page && board.reset(page)}>
          <Icon name="SYNC" size={12} /><span class="label">{t("scanner_reset_corners")}</span>
        </button>
      </div>

      <div class="work" bind:clientWidth={workW} bind:clientHeight={workH}>
        <div class="strip" style:width="{stripWidth}px">
          <PageStrip {board} />
        </div>
        <!-- A focusable separator is a control (WAI-ARIA window splitter); Svelte counts it as static. -->
        <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
        <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
        <div class="sash" role="separator" aria-orientation="vertical" aria-valuenow={stripWidth}
             aria-label={t("scanner_pages")} tabindex="0" onpointerdown={sashDown} onpointermove={sashMove}
             onpointerup={sashUp} onpointercancel={sashUp} ondblclick={() => board.saveStrip(0)} onkeydown={sashKey}>
          <span class="grip"></span>
        </div>
        <div class="stage">
          {#if page}
            <CornerEditor {page} {locked} oncommit={commit} />
          {:else}
            <button class="empty" type="button" disabled={locked} onclick={addPhotos}>
              <Icon name="SCAN" size={30} />
              <span class="body">{t("scanner_empty_canvas")}</span>
            </button>
          {/if}
        </div>
      </div>

      <p class="hint corners">{t("scanner_corners_hint")}</p>
      <div class="options">
        <label class="field-label" for="scanner-mode">{t("scanner_scan_mode")}</label>
        <span class="select-wrap mode">
          <select id="scanner-mode" class="select" value={board.mode}
                  onchange={(event) => board.setMode(event.currentTarget.value as ScanMode)}>
            {#each MODES as option (option.mode)}
              <option value={option.mode}>{t(option.label)}</option>
            {/each}
          </select>
        </span>
        <label class="field-label" for="scanner-output">{t("scanner_output_pdf")}</label>
        <div class="row">
          <input id="scanner-output" class="input grow" type="text" dir="auto" spellcheck="false"
                 value={board.output} onchange={(event) => typedOutput(event.currentTarget.value)} />
          <button class="btn btn-secondary" type="button" onclick={chooseOutput}>{t("str_save")}</button>
        </div>
      </div>
      <ProgressFooter {run} label={t("scanner_btn")} onaction={exportPdf} disabled={locked} {working} />
    </section>

    <section class="side card" aria-label={t("scanner_preview")}>
      <h2 class="heading">{t("scanner_preview")}</h2>
      <div class="preview">
        {#if preview}
          <img src={preview} alt={t("scanner_preview")} class:loaded={previewLoaded}
               onload={() => (previewLoaded = true)} onerror={() => (previewLoaded = true)} />
        {/if}
      </div>
      <div class="result"><FeedbackPanel {feedback} /></div>
    </section>
  </div>
</div>

{#if fullscreen && page}
  <div class="crop" role="dialog" aria-modal="true" aria-label={t("scanner_fullscreen_crop")} tabindex="-1"
       onkeydown={overlayKey} use:focusNode>
    <div class="crop-bar">
      <p class="body grow">{t("scanner_corners_hint")}</p>
      <button class="btn btn-primary" type="button" title="Esc" onclick={() => (fullscreen = false)}>
        {t("scanner_fullscreen_close")}
      </button>
    </div>
    <div class="crop-stage">
      <CornerEditor {page} large {locked} oncommit={commit} />
    </div>
  </div>
{/if}

<style>
  .scanner {
    display: flex;
    flex-direction: column;
    height: 100%;
    min-height: 0;
  }
  .hint-strip {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    margin: 0 0 12px;
    padding: 7px 12px;
    background: var(--sunken);
    border-radius: var(--radius);
    color: var(--text-secondary);
  }
  .hint-strip :global(.icon) {
    color: var(--text-tertiary);
    margin-top: 2px;
    flex: none;
  }
  .body {
    flex: 1 1 auto;
    min-height: 0;
    display: flex;
    gap: 16px;
  }
  .editor-card {
    flex: 1 1 auto;
    min-width: 0;
    display: flex;
    flex-direction: column;
    padding: 16px;
    overflow-y: auto;
  }
  .toolbar {
    display: flex;
    align-items: center;
    gap: 4px;
    margin-bottom: 8px;
    container-type: inline-size;
    min-width: 0;
  }
  .toolbar .btn:first-child {
    margin-inline-end: 4px;
  }
  .separator {
    width: 1px;
    align-self: stretch;
    margin: 4px 8px;
    background: var(--border-subtle);
  }
  /* Too narrow for the words: the buttons keep their icons and tooltips. */
  @container (max-width: 540px) {
    .collapse .label {
      display: none;
    }
  }
  .work {
    flex: 1 1 auto;
    min-height: 220px;
    display: flex;
  }
  .strip {
    flex: none;
    min-width: 0;
  }
  .sash {
    flex: none;
    width: 10px;
    display: grid;
    place-items: center;
    cursor: col-resize;
    touch-action: none;
  }
  .grip {
    width: 4px;
    height: 48px;
    border-radius: 2px;
    background: var(--border);
  }
  .sash:hover .grip,
  .sash:focus-visible .grip {
    background: var(--accent);
  }
  .stage {
    flex: 1 1 auto;
    min-width: 0;
    display: flex;
  }
  .empty {
    flex: 1;
    display: grid;
    align-content: center;
    justify-items: center;
    gap: 16px;
    padding: 24px 40px;
    border: 0;
    border-radius: var(--radius);
    background: var(--stage);
    color: var(--stage-text);
    text-align: center;
  }
  .empty :global(.icon) {
    color: var(--stage-muted);
  }
  .corners {
    margin: 6px 0 0;
  }
  .options {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    align-items: center;
    gap: 8px 12px;
    margin-top: 12px;
  }
  .options .field-label {
    margin: 0;
  }
  .mode {
    width: min(100%, 340px);
  }
  .side {
    width: 280px;
    flex: none;
    display: flex;
    flex-direction: column;
    padding: 16px;
    min-height: 0;
  }
  h2 {
    margin: 0 0 10px;
  }
  .preview {
    flex: 1 1 auto;
    min-height: 140px;
    display: grid;
    place-items: center;
    padding: 12px;
    background: var(--sunken);
    border-radius: var(--radius);
    overflow: hidden;
  }
  .preview img {
    max-width: 100%;
    max-height: 100%;
    display: block;
    background: var(--surface);
    box-shadow: 1px 3px 0 var(--border-subtle);
    opacity: 0;
    transition: opacity 120ms ease-out;
  }
  .preview img.loaded {
    opacity: 1;
  }
  .result {
    margin-top: 14px;
  }
  /* A short window: the photo keeps the room, the extras give it up. */
  @media (max-height: 760px) {
    .corners {
      display: none;
    }
    .work {
      min-height: 150px;
    }
    .toolbar {
      margin-bottom: 6px;
    }
    .options {
      margin-top: 8px;
      gap: 6px 12px;
    }
    .editor-card :global(.footer) {
      margin-top: 12px;
    }
    .editor-card :global(.footer .divider) {
      margin-bottom: 10px;
    }
  }
  @media (max-width: 1180px) {
    .side {
      width: 240px;
    }
  }
  .crop {
    position: fixed;
    inset: 0;
    z-index: 20;
    display: flex;
    flex-direction: column;
    background: var(--stage);
  }
  .crop:focus {
    outline: none;
  }
  .crop-bar {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 20px;
    background: var(--surface);
    border-bottom: 1px solid var(--border-subtle);
  }
  .crop-bar p {
    margin: 0;
  }
  .crop-stage {
    flex: 1 1 auto;
    min-height: 0;
    display: flex;
  }
</style>
