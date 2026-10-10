<script lang="ts">
  // The full PDF viewer (pdf_viewer.py), inside the window: one page at a
  // time on the dark stage, zoom 50–500 %, and the same keys.
  import { api } from "../lib/bridge";
  import { app } from "../lib/app.svelte";
  import { t } from "../lib/i18n.svelte";
  import type { PdfDocument } from "../lib/types";
  import Icon from "./Icon.svelte";

  let { path }: { path: string } = $props();
  let doc = $state<PdfDocument | null>(null);
  let page = $state(0);
  let zoom = $state(1);
  let loaded = $state(false);
  let stage: HTMLElement | undefined = $state();
  let previous: Element | null = null;

  $effect(() => {
    let current = true;
    api().document(path).then((result) => {
      if (current) doc = result;
    });
    previous = document.activeElement;
    stage?.focus();
    return () => {
      current = false;
      (previous as HTMLElement | null)?.focus?.();
    };
  });

  let total = $derived(doc?.pages ?? 0);
  let width = $derived(Math.round((doc?.width ?? 595) * zoom));
  let height = $derived(Math.round((doc?.height ?? 842) * zoom));
  let render = $derived(Math.min(4096, Math.ceil((width * (window.devicePixelRatio || 1)) / 160) * 160));
  let src = $derived(doc?.base ? `${doc.base}${page}?w=${render}&v=${doc.version}` : null);

  function show(index: number) {
    if (index < 0 || index >= total || index === page) return;
    page = index;
    loaded = false;
    stage?.scrollTo({ top: 0 });
  }

  function zoomBy(step: number) {
    const next = Math.round((zoom + step) * 2) / 2;
    if (next >= 0.5 && next <= 5) {
      zoom = next;
      loaded = false;
    }
  }

  function close() {
    app.viewer = null;
  }

  function key(event: KeyboardEvent) {
    const rtl = document.documentElement.dir === "rtl";
    const actions: Record<string, () => void> = {
      ArrowLeft: () => show(page + (rtl ? 1 : -1)),
      ArrowRight: () => show(page + (rtl ? -1 : 1)),
      PageUp: () => show(page - 1),
      PageDown: () => show(page + 1),
      Home: () => show(0),
      End: () => show(total - 1),
      "+": () => zoomBy(0.5),
      "-": () => zoomBy(-0.5),
      Escape: close,
    };
    const action = actions[event.key];
    if (action) {
      event.preventDefault();
      event.stopPropagation();
      action();
    }
  }
</script>

<div class="viewer" role="dialog" aria-modal="true" aria-label={doc?.name ?? t("viewer_title")} tabindex="-1"
     onkeydown={key}>
  <div class="toolbar">
    <button class="btn btn-ghost" title="← / PgUp" disabled={page === 0} onclick={() => show(page - 1)}>
      <Icon name="LEFT" size={13} flip />{t("viewer_prev")}
    </button>
    <span class="body page">{t("viewer_page", { current: page + 1, total })}</span>
    <button class="btn btn-ghost" title="→ / PgDn" disabled={page >= total - 1} onclick={() => show(page + 1)}>
      {t("viewer_next")}<Icon name="RIGHT" size={13} flip />
    </button>
    <span class="sep"></span>
    <button class="btn btn-ghost" title="−" disabled={zoom <= 0.5} onclick={() => zoomBy(-0.5)}>
      <Icon name="ZOOM_OUT" size={13} />{t("viewer_zoom_out")}
    </button>
    <button class="btn btn-ghost" title="+" disabled={zoom >= 5} onclick={() => zoomBy(0.5)}>
      <Icon name="ZOOM_IN" size={13} />{t("viewer_zoom_in")}
    </button>
    <span class="small faint">{Math.round(zoom * 100)}%</span>
    <span class="grow name small muted ellipsis">{doc?.name ?? ""}</span>
    <button class="btn btn-secondary" title="Esc" onclick={close}>
      <Icon name="CLOSE" size={12} />{t("str_close")}
    </button>
  </div>
  <div class="stage" bind:this={stage} tabindex="-1">
    {#if src}
      <img {src} alt={t("viewer_page", { current: page + 1, total })} class:loaded style:width="{width}px"
           style:height="{height}px" onload={() => (loaded = true)} />
    {/if}
  </div>
</div>

<style>
  .viewer {
    position: fixed;
    inset: 0;
    z-index: 20;
    display: flex;
    flex-direction: column;
    background: var(--stage);
  }
  .toolbar {
    display: flex;
    align-items: center;
    gap: 2px;
    padding: 8px 16px;
    background: var(--surface);
    border-bottom: 1px solid var(--border-subtle);
  }
  .page {
    padding: 0 12px;
  }
  .sep {
    width: 1px;
    align-self: stretch;
    margin: 4px 12px;
    background: var(--border-subtle);
  }
  .name {
    padding: 0 12px;
    text-align: end;
  }
  .viewer:focus,
  .stage:focus {
    outline: none;
  }
  .stage {
    flex: 1 1 auto;
    overflow: auto;
    display: grid;
    padding: 24px;
  }
  img {
    margin: auto;
    display: block;
    background: var(--surface);
    opacity: 0.35;
    transition: opacity 100ms ease-out;
  }
  img.loaded {
    opacity: 1;
  }
</style>
