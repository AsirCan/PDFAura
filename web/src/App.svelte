<script lang="ts">
  // The window: sidebar, page header with the assistant, the open tool (or
  // Settings), the preview, and the full viewer over everything.
  import { onMount, type Component } from "svelte";
  import { SvelteSet } from "svelte/reactivity";
  import { api, connect } from "./lib/bridge";
  import { app, followSystemTheme, listen, NAV, OWN_PREVIEW, PAGES, showPage, type Page } from "./lib/app.svelte";
  import { dialogs } from "./lib/dialog.svelte";
  import { t } from "./lib/i18n.svelte";
  import ConfirmDialog from "./components/ConfirmDialog.svelte";
  import Header from "./components/Header.svelte";
  import PreviewPanel from "./components/PreviewPanel.svelte";
  import Settings from "./components/Settings.svelte";
  import Sidebar from "./components/Sidebar.svelte";
  import Viewer from "./components/Viewer.svelte";
  import Advanced from "./tools/Advanced.svelte";
  import Batch from "./tools/Batch.svelte";
  import Compress from "./tools/Compress.svelte";
  import Convert from "./tools/Convert.svelte";
  import Organize from "./tools/Organize.svelte";
  import Scanner from "./tools/Scanner.svelte";
  import Security from "./tools/Security.svelte";

  const TOOLS: Record<Page, Component> = {
    compress: Compress, organize: Organize, scanner: Scanner, convert: Convert, security: Security,
    advanced: Advanced, batch: Batch,
  };

  let command: HTMLInputElement | undefined = $state();
  let failed = $state<string | null>(null);
  // A tool is built the first time it is opened and then kept, so going
  // back to it finds the files and choices where they were.
  const opened = new SvelteSet<Page>(["compress"]);

  $effect(() => {
    opened.add(app.page);
  });

  $effect(() => {
    document.documentElement.dataset.theme = app.shown;
    if (app.ready) void api().theme_shown(app.shown);
  });

  onMount(() => {
    const stops = [listen(), followSystemTheme()];
    connect()
      .then((bridge) => bridge.boot())
      .then((boot) => app.load(boot))
      .catch((error) => {
        failed = String(error);
      });
    return () => stops.forEach((stop) => stop());
  });

  function key(event: KeyboardEvent) {
    if (dialogs.open || app.viewer) return;
    if (event.ctrlKey && !event.altKey && !event.shiftKey) {
      const index = Number(event.key) - 1;
      if (index >= 0 && index < NAV.length) {
        event.preventDefault();
        app.settingsOpen = false;
        showPage(NAV[index].page);
      } else if (event.key.toLowerCase() === "k") {
        event.preventDefault();
        command?.focus();
      } else if (event.key === ",") {
        event.preventDefault();
        app.settingsOpen = true;
      }
    } else if (event.key === "Escape" && app.settingsOpen) {
      app.settingsOpen = false;
    }
  }
</script>

<svelte:window onkeydown={key} />

{#if failed}
  <p class="boot-error body">{failed}</p>
{:else if app.ready}
  <div class="shell">
    <Sidebar />
    <main class="main">
      <Header bind:command />
      <div class="body">
        <div class="content">
          {#if app.settingsOpen}
            <Settings />
          {/if}
          {#each PAGES as page (page)}
            {#if opened.has(page)}
              {@const Tool = TOOLS[page]}
              <section class="page" hidden={app.settingsOpen || app.page !== page}
                       aria-label={t(`page_meta_${page}_title`)}>
                <Tool />
              </section>
            {/if}
          {/each}
        </div>
        {#if !app.settingsOpen && !OWN_PREVIEW.includes(app.page)}
          <PreviewPanel />
        {/if}
      </div>
    </main>
  </div>
  {#if app.viewer}
    <Viewer path={app.viewer} />
  {/if}
  <ConfirmDialog />
{/if}

<style>
  .shell {
    display: flex;
    height: 100%;
  }
  .main {
    flex: 1 1 auto;
    min-width: 0;
    display: flex;
    flex-direction: column;
    padding: 22px 28px 24px;
  }
  .body {
    flex: 1 1 auto;
    min-height: 0;
    display: flex;
    gap: 20px;
    margin-top: 18px;
  }
  .content {
    flex: 1 1 auto;
    min-width: 440px;
    min-height: 0;
  }
  .page {
    height: 100%;
  }
  .page[hidden] {
    display: none;
  }
  .boot-error {
    margin: 40px;
    color: var(--danger);
  }
</style>
