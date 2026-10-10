<script lang="ts">
  // The page title and the assistant bar above every tool.
  import { app } from "../lib/app.svelte";
  import { t } from "../lib/i18n.svelte";
  import CommandBar from "./CommandBar.svelte";
  import Icon from "./Icon.svelte";

  let { command = $bindable() }: { command?: HTMLInputElement } = $props();
  let key = $derived(app.settingsOpen ? null : app.page);
</script>

<header class="header">
  <div class="titles">
    {#if key}
      <p class="eyebrow micro">{t(`page_meta_${key}_eyebrow`)}</p>
      <h1 class="display">{t(`page_meta_${key}_title`)}</h1>
      <p class="lead body">{t(`page_meta_${key}_body`)}</p>
    {:else}
      <h1 class="display">{t("txt_settings")}</h1>
      <p class="lead body">{t("settings_intro_web")}</p>
    {/if}
  </div>
  <CommandBar bind:input={command} />
</header>

{#if app.reply}
  <div class="reply" role="status">
    <Icon name="SPARK" size={13} />
    <p class="body selectable">{app.reply}</p>
    <button class="close small" title={t("str_close")} aria-label={t("str_close")} onclick={() => (app.reply = null)}>
      <Icon name="CLOSE" size={10} />
    </button>
  </div>
{/if}

<style>
  .header {
    display: flex;
    align-items: flex-start;
    gap: 24px;
  }
  .titles {
    flex: 1 1 auto;
    min-width: 0;
  }
  .eyebrow {
    margin: 0;
    color: var(--text-tertiary);
  }
  h1 {
    margin: 2px 0 0;
  }
  .lead {
    margin: 4px 0 0;
    color: var(--text-secondary);
  }
  .header :global(.command) {
    margin-top: 6px;
  }
  .reply {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    margin-top: 14px;
    padding: 8px 6px 8px 12px;
    background: var(--accent-subtle);
    border: 1px solid var(--accent-border);
    border-radius: var(--radius);
    color: var(--accent-text);
  }
  .reply > :global(.icon) {
    margin-top: 3px;
  }
  .reply p {
    flex: 1 1 auto;
    margin: 0;
    color: var(--text);
    white-space: pre-line;
  }
  .close {
    border: 0;
    background: transparent;
    color: var(--accent-text);
    border-radius: var(--radius-sm);
    padding: 4px 6px;
  }
  .close:hover {
    background: var(--accent-subtle-hover);
  }
</style>
