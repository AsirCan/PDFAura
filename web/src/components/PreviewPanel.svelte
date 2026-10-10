<script lang="ts">
  // The first page of the selected PDF on a paper-grey stage, with its name,
  // size and shortcuts. Python draws the page; nothing here blocks.
  import { api } from "../lib/bridge";
  import { app } from "../lib/app.svelte";
  import { t } from "../lib/i18n.svelte";
  import type { PdfDocument } from "../lib/types";
  import Icon from "./Icon.svelte";

  const PAD = 22;
  let doc = $state<PdfDocument | null>(null);
  let stageWidth = $state(0);
  let stageHeight = $state(0);
  let loaded = $state(false);

  $effect(() => {
    const path = app.preview;
    doc = null;
    loaded = false;
    if (!path) return;
    let current = true;
    api().document(path).then((result) => {
      if (current) doc = result;
    });
    return () => {
      current = false;
    };
  });

  // The page fitted into the stage, and the width Python renders it at
  // (rounded up, so a small resize does not ask for a new picture).
  let fit = $derived.by(() => {
    if (!doc?.width || !doc.height || !stageWidth || !stageHeight) return null;
    const scale = Math.min((stageWidth - PAD * 2) / doc.width, (stageHeight - PAD * 2) / doc.height);
    const width = Math.max(1, Math.floor(doc.width * scale));
    const height = Math.max(1, Math.floor(doc.height * scale));
    // At least 1.5x the shown size: a downscaled page reads smoother than
    // one drawn at exactly its size (Tk's panel drew at 560 px and scaled).
    const render = Math.min(2400, Math.ceil((width * Math.max(window.devicePixelRatio || 1, 1.5)) / 160) * 160);
    return { width, height, render };
  });

  let src = $derived(doc?.base && fit ? `${doc.base}0?w=${fit.render}&v=${doc.version}` : null);
  let failed = $derived(Boolean(doc?.error && doc.error !== "not-a-pdf"));
  let sizeMb = $derived(doc ? doc.size / (1024 * 1024) : 0);

  function openViewer() {
    if (doc && !doc.error) app.viewer = doc.path;
  }
</script>

<aside class="preview card" aria-label={t("preview_title")}>
  <h2 class="heading">{t("preview_title")}</h2>
  <p class="subtitle small">{t("preview_subtitle")}</p>

  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="stage" bind:clientWidth={stageWidth} bind:clientHeight={stageHeight} ondblclick={openViewer}>
    {#if src && fit && !failed}
      <img
        {src}
        alt={doc?.name ?? ""}
        class:loaded
        style:width="{fit.width}px"
        style:height="{fit.height}px"
        onload={() => (loaded = true)}
        onerror={() => (loaded = true)}
      />
    {:else if failed}
      <p class="failed body-strong">{t("preview_unavailable")}</p>
    {:else if !app.preview}
      <div class="empty">
        <Icon name="DOCUMENT" size={34} />
        <p class="body-strong">{t("preview_empty_title")}</p>
        <p class="small muted">{t("str_drag_drop_hint")}</p>
      </div>
    {/if}
  </div>

  {#if doc}
    <div class="info">
      <p class="name body-strong selectable" dir="auto">{doc.name}</p>
      <p class="small muted">
        {failed ? doc.error : t("preview_pages_mb", { pages: doc.pages ?? 0, size: sizeMb })}
      </p>
      <p class="folder small faint selectable" dir="auto">{doc.folder}</p>
    </div>
  {/if}

  <div class="actions">
    <button class="btn btn-secondary" disabled={!doc || failed} onclick={openViewer}>
      <Icon name="OPEN" size={13} />{t("preview_open")}
    </button>
    <button class="btn btn-ghost" disabled={!doc} onclick={() => doc && api().reveal_path(doc.path)}>
      <Icon name="FOLDER" size={13} />{t("preview_open_folder")}
    </button>
  </div>
</aside>

<style>
  .preview {
    width: 320px;
    flex: none;
    display: flex;
    flex-direction: column;
    padding: 18px;
    min-height: 0;
  }
  h2 {
    margin: 0;
  }
  .subtitle {
    margin: 2px 0 0;
    color: var(--text-secondary);
  }
  .stage {
    position: relative;
    flex: 1 1 auto;
    min-height: 160px;
    margin-top: 14px;
    display: grid;
    place-items: center;
    background: var(--sunken);
    border-radius: var(--radius);
    overflow: hidden;
  }
  img {
    display: block;
    background: var(--surface);
    border: 1px solid var(--border-subtle);
    box-shadow: 1px 3px 0 var(--border-subtle);
    opacity: 0;
    transition: opacity 120ms ease-out;
  }
  img.loaded {
    opacity: 1;
  }
  .empty {
    position: absolute;
    inset: 12px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 6px;
    padding: 0 18px;
    text-align: center;
    border: 1px dashed var(--border);
    border-radius: var(--radius-sm);
    color: var(--text-tertiary);
  }
  .empty p {
    margin: 0;
  }
  .empty .body-strong {
    margin-top: 6px;
    color: var(--text);
  }
  .failed {
    color: var(--danger);
    text-align: center;
    padding: 0 20px;
  }
  .info {
    margin-top: 14px;
  }
  .info p {
    margin: 0;
    overflow-wrap: anywhere;
  }
  .info .folder {
    margin-top: 6px;
  }
  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 14px;
  }
</style>
