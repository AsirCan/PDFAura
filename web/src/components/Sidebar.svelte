<script lang="ts">
  // The navigation rail: the tools, the recent files and Settings.
  import { api } from "../lib/bridge";
  import { app, NAV, refreshRecent, showPage } from "../lib/app.svelte";
  import { t } from "../lib/i18n.svelte";
  import Icon from "./Icon.svelte";

  async function openRecent(path: string) {
    // A file deleted since drops out of the list instead of failing.
    if (!(await api().open_path(path))) await refreshRecent();
  }
</script>

<nav class="sidebar" aria-label={t("sidebar_workspace")}>
  <div class="brand">
    <img src="./app-icon.png" alt="" width="26" height="26" />
    <span class="heading">PDF Aura</span>
  </div>

  <p class="section micro">{t("sidebar_workspace")}</p>
  <ul class="nav">
    {#each NAV as item, index (item.page)}
      <li>
        <button
          class="nav-item body"
          class:selected={app.page === item.page && !app.settingsOpen}
          aria-current={app.page === item.page && !app.settingsOpen ? "page" : undefined}
          title={`Ctrl+${index + 1}`}
          onclick={() => {
            app.settingsOpen = false;
            showPage(item.page);
          }}
        >
          <Icon name={item.icon} />
          <span class="ellipsis">{t(item.label)}</span>
        </button>
      </li>
    {/each}
  </ul>

  <p class="section micro">{t("sidebar_recent")}</p>
  <div class="recent">
    {#if app.recent.length === 0}
      <p class="empty small">{t("sidebar_recent_empty")}</p>
    {:else}
      <ul>
        {#each app.recent as file (file.path)}
          <li>
            <button class="recent-item small" title={file.path} onclick={() => openRecent(file.path)}>
              <Icon name="DOCUMENT" size={13} />
              <span class="ellipsis">{file.name}</span>
            </button>
          </li>
        {/each}
      </ul>
    {/if}
  </div>

  <div class="bottom">
    <hr class="divider" />
    <button
      class="nav-item body"
      class:selected={app.settingsOpen}
      title="Ctrl+,"
      onclick={() => (app.settingsOpen = true)}
    >
      <Icon name="SETTINGS" />
      <span class="ellipsis">{t("txt_settings")}</span>
    </button>
    <p class="offline small">
      <Icon name="SHIELD" size={12} />
      <span>{t("sidebar_offline")}</span>
    </p>
  </div>
</nav>

<style>
  .sidebar {
    width: var(--sidebar-width);
    flex: none;
    display: flex;
    flex-direction: column;
    background: var(--sidebar);
    border-inline-end: 1px solid var(--border-subtle);
    padding: 18px 12px 14px;
    min-height: 0;
  }
  .brand {
    display: flex;
    align-items: center;
    gap: 10px;
    padding-inline-start: 8px;
  }
  .brand img {
    object-fit: contain;
  }
  .section {
    color: var(--text-tertiary);
    margin: 26px 0 6px;
    padding-inline-start: 10px;
  }
  .section + .recent {
    min-height: 0;
  }
  ul {
    list-style: none;
    margin: 0;
    padding: 0;
  }
  .nav li + li {
    margin-top: 2px;
  }
  .nav-item {
    width: 100%;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 7px 10px;
    border: 1px solid transparent;
    border-radius: var(--radius);
    background: transparent;
    color: var(--text-secondary);
    text-align: start;
  }
  .nav-item :global(.icon) {
    color: var(--text-tertiary);
  }
  .nav-item:hover {
    background: var(--hover);
    color: var(--text);
  }
  .nav-item:hover :global(.icon) {
    color: var(--text);
  }
  .nav-item:active {
    background: var(--pressed);
  }
  .nav-item.selected {
    background: var(--surface);
    border-color: var(--border-subtle);
    color: var(--text);
  }
  .nav-item.selected :global(.icon) {
    color: var(--accent);
  }
  .recent {
    flex: 1 1 auto;
    overflow-y: auto;
  }
  .empty {
    margin: 0;
    padding-inline-start: 10px;
    color: var(--text-tertiary);
  }
  .recent-item {
    width: 100%;
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 4px 10px;
    border: 0;
    border-radius: var(--radius);
    background: transparent;
    color: var(--text-secondary);
    text-align: start;
  }
  .recent-item :global(.icon) {
    color: var(--text-tertiary);
    flex: none;
  }
  .recent-item:hover {
    background: var(--hover);
    color: var(--text);
  }
  .bottom {
    flex: none;
    padding-top: 8px;
  }
  .bottom .divider {
    margin-bottom: 8px;
  }
  .offline {
    display: flex;
    gap: 6px;
    align-items: flex-start;
    margin: 10px 0 0;
    padding-inline-start: 10px;
    color: var(--text-tertiary);
  }
  .offline :global(.icon) {
    margin-top: 3px;
    flex: none;
  }
</style>
