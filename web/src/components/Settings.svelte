<script lang="ts">
  // Settings, in the window rather than a second one: General (theme,
  // language, tray, sound, default output folder) and Local AI (models).
  // Theme and language change at once; the rest on Save.
  import { onDestroy } from "svelte";
  import { api, on } from "../lib/bridge";
  import { app, refreshRecent, setLanguage, setTheme } from "../lib/app.svelte";
  import { language, t } from "../lib/i18n.svelte";
  import { Feedback } from "../lib/run.svelte";
  import type { ModelRow, ThemePreference } from "../lib/types";
  import FeedbackPanel from "./Feedback.svelte";
  import Icon from "./Icon.svelte";
  import Segmented from "./Segmented.svelte";
  import ThemeCard from "./ThemeCard.svelte";

  type Tab = "general" | "ai";
  let tab = $state<Tab>("general");
  let tray = $state(app.settings.close_to_tray);
  let sound = $state(app.settings.sound_enabled);
  let folder = $state(app.settings.default_output_dir);
  let feedback = new Feedback(() => t("txt_settings"), () => t("settings_intro_web"));

  const THEMES: { value: ThemePreference; label: string }[] = [
    { value: "paper", label: "settings_theme_light" },
    { value: "night", label: "settings_theme_dark" },
    { value: "system", label: "settings_theme_system" },
  ];

  async function save() {
    try {
      app.settings = await api().save_settings({ close_to_tray: tray, sound_enabled: sound,
                                                 default_output_dir: folder.trim() });
      if (root.trim() && root.trim() !== models?.root) await saveRoot(root.trim());
      feedback.success(() => t("str_success"), () => t("settings_saved"));
    } catch {
      feedback.error(() => t("str_error"), () => t("settings_folder_missing"));
    }
  }

  async function pickFolder() {
    const chosen = await api().pick_folder(folder);
    if (chosen) folder = chosen.path;
  }

  async function clearHistory() {
    await api().clear_recent();
    await refreshRecent();
    feedback.success(() => t("str_success"), () => t("settings_cleared"));
  }

  // ── Local AI ──────────────────────────────────────────────────────
  let models = $state<{ root: string; rows: ModelRow[] } | null>(null);
  let root = $state("");
  let selected = $state<string | null>(null);
  let downloading = $state<{ job: number; percent: number } | null>(null);
  let testing = $state(false);
  let row = $derived(models?.rows.find((item) => item.id === selected) ?? null);

  async function loadModels(useRoot?: string) {
    models = await api().models(useRoot ?? null);
    root = models.root;
  }

  async function saveRoot(path: string) {
    models = await api().models_save_root(path);
    root = models.root;
  }

  async function pickRoot() {
    const chosen = await api().pick_folder(root);
    if (!chosen) return;
    await saveRoot(chosen.path);
    feedback.success(() => t("str_success"), () => t("settings_ai_root_saved"));
  }

  async function pickModelPath() {
    if (!selected) return feedback.info(() => t("settings_local_ai_title"), () => t("settings_ai_no_selection"));
    const updated = await api().models_pick_path(selected);
    if (updated) {
      models = updated;
      feedback.success(() => t("str_success"), () => t("settings_ai_path_saved"));
    }
  }

  async function download() {
    if (!selected) return feedback.info(() => t("settings_local_ai_title"), () => t("settings_ai_no_selection"));
    if (downloading) return;
    const result = await api().models_download(selected);
    if (result.job === undefined) {
      feedback.info(() => t("settings_local_ai_title"), () => t("settings_ai_download_unavailable"));
      return;
    }
    downloading = { job: result.job, percent: 0 };
    feedback.busy(t("settings_ai_download_started"));
  }

  function test() {
    if (!selected) return feedback.info(() => t("settings_local_ai_title"), () => t("settings_ai_no_selection"));
    testing = true;
    void api().models_test(selected);
  }

  const stops = [
    on("job", (event) => {
      if (!downloading || event.id !== downloading.job) return;
      if (event.type === "progress") {
        downloading.percent = Math.floor((event.current / Math.max(1, event.total)) * 100);
        return;
      }
      downloading = null;
      if (event.type === "done") feedback.success(event.outcome.title, event.outcome.message);
      else if (event.type === "failed") feedback.error(event.title, event.message);
      else feedback.cancelled();
      void loadModels(root);
    }),
    on("model-test", (event) => {
      testing = false;
      if (event.ok) feedback.success(() => t("settings_ai_test_ok"), event.message);
      else feedback.error(() => t("settings_ai_test_fail"), event.message);
      void loadModels(root);
    }),
  ];
  onDestroy(() => stops.forEach((stop) => stop()));

  $effect(() => {
    if (tab === "ai" && !models) void loadModels();
  });
</script>

<div class="settings">
  <div class="main">
    <Segmented
      canvas
      label={t("txt_settings")}
      bind:value={tab}
      options={[{ value: "general", label: t("settings_general_tab") },
                { value: "ai", label: t("settings_local_ai_tab") }]}
    />

    <div class="scroll">
      {#if tab === "general"}
        <section class="card form">
          <h2 class="section-title">{t("settings_appearance")}</h2>
          <p class="field-label spaced">{t("settings_theme")}</p>
          <div class="themes" role="radiogroup" aria-label={t("settings_theme")}>
            {#each THEMES as choice (choice.value)}
              <ThemeCard value={choice.value} label={t(choice.label)} selected={app.theme === choice.value}
                         onchoose={(value) => setTheme(value)} />
            {/each}
          </div>
          <p class="hint">{t("settings_theme_hint")}</p>

          <div class="row language">
            <label class="field-label inline" for="settings-language">{t("settings_lang")}</label>
            <span class="select-wrap">
              <select id="settings-language" class="select" value={language.code}
                      onchange={(event) => setLanguage((event.currentTarget as HTMLSelectElement).value)}>
                {#each app.languages as [code, name] (code)}
                  <option value={code}>{name}</option>
                {/each}
              </select>
            </span>
          </div>

          <label class="check"><input type="checkbox" bind:checked={tray} />{t("settings_tray")}</label>
          <label class="check"><input type="checkbox" bind:checked={sound} />{t("settings_sound")}</label>

          <hr class="divider gap" />
          <h2 class="section-title">{t("settings_file_ops")}</h2>
          <label class="field-label spaced" for="settings-folder">{t("settings_default_dir")}</label>
          <div class="row">
            <input id="settings-folder" class="input grow" bind:value={folder} spellcheck="false" />
            <button class="btn btn-ghost" onclick={() => (folder = "")}><Icon name="CLEAR" size={12} />{t("str_delete")}</button>
            <button class="btn btn-secondary" onclick={pickFolder}>{t("str_select")}</button>
          </div>

          <div class="row buttons">
            <button class="btn btn-primary" onclick={save}>{t("settings_save_btn")}</button>
            <button class="btn btn-secondary" onclick={clearHistory}>{t("settings_clear_history")}</button>
          </div>
        </section>
      {:else}
        <section class="card form">
          <h2 class="section-title">{t("settings_local_ai_title")}</h2>
          <p class="hint">{t("settings_local_ai_desc")}</p>

          <label class="field-label spaced" for="settings-model-root">{t("settings_ai_model_root")}</label>
          <div class="row">
            <input id="settings-model-root" class="input grow" bind:value={root} spellcheck="false" />
            <button class="btn btn-secondary" onclick={() => api().open_path(root)}>{t("settings_ai_open_folder")}</button>
            <button class="btn btn-secondary" onclick={pickRoot}>{t("str_select")}</button>
          </div>

          <div class="table-wrap">
            <table>
              <thead>
                <tr class="label">
                  <th>{t("settings_ai_status")}</th><th>{t("settings_ai_model")}</th><th>{t("settings_ai_type")}</th>
                  <th class="num">{t("settings_ai_size")}</th><th>{t("settings_ai_hardware")}</th>
                </tr>
              </thead>
              <tbody>
                {#each models?.rows ?? [] as model (model.id)}
                  <tr class:selected={model.id === selected} onclick={() => (selected = model.id)}>
                    <td>
                      <label class="pick">
                        <input type="radio" name="model" value={model.id} bind:group={selected} />
                        <span class="status" class:ready={model.installed}>
                          {t(model.installed ? "settings_ai_ready" : "settings_ai_missing")}
                        </span>
                      </label>
                    </td>
                    <td>{model.name}</td><td>{model.category}</td><td class="num">{model.size}</td><td>{model.hardware}</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>

          <div class="row buttons wrap">
            <button class="btn btn-secondary" onclick={() => loadModels(root)}>{t("settings_ai_refresh")}</button>
            <button class="btn btn-secondary" onclick={pickModelPath}>{t("settings_ai_pick_model")}</button>
            <button class="btn btn-secondary" disabled={Boolean(downloading)} onclick={download}>
              {t("settings_ai_download")}
            </button>
            <button class="btn btn-secondary" disabled={testing} onclick={test}>{t("settings_ai_test")}</button>
            <span class="grow"></span>
            <button class="btn btn-primary" onclick={save}>{t("settings_save_btn")}</button>
          </div>

          <div class="detail small muted selectable">
            {#if row}
              <p class="body-strong">{row.name}</p>
              {#if downloading && row.id === selected}
                <p>{t("model_detail_downloading")}: {downloading.percent}%</p>
              {/if}
              <p>{row.description}</p>
              <p>{t("model_detail_status")}: {row.message}</p>
              <p>{t("model_detail_path")}: {row.path || "-"}</p>
              <p>{t("model_detail_license")}: {row.license || "-"}</p>
              <p>{t("model_detail_notes")}: {row.notes || "-"}</p>
            {:else}
              <p>{t("settings_ai_no_selection")}</p>
            {/if}
          </div>
        </section>
      {/if}
    </div>
  </div>

  <aside class="side card">
    <FeedbackPanel {feedback} />
  </aside>
</div>

<style>
  .settings {
    display: flex;
    gap: 18px;
    min-height: 0;
    height: 100%;
  }
  .main {
    flex: 1 1 auto;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 12px;
    min-height: 0;
  }
  .main > :global(.segmented) {
    align-self: flex-start;
  }
  .scroll {
    flex: 1 1 auto;
    min-height: 0;
    overflow-y: auto;
    scrollbar-gutter: stable;
  }
  .form {
    padding: 20px;
  }
  .side {
    width: 300px;
    flex: none;
    align-self: flex-start;
    padding: 16px;
    margin-top: 46px;
  }
  .spaced {
    margin-top: 14px;
  }
  .themes {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
  }
  .hint {
    margin: 8px 0 0;
  }
  .language {
    margin-top: 18px;
  }
  .field-label.inline {
    margin: 0;
  }
  .check {
    display: flex;
    margin-top: 10px;
  }
  .language + .check {
    margin-top: 16px;
  }
  .gap {
    margin: 18px 0;
  }
  .buttons {
    margin-top: 18px;
  }
  .wrap {
    flex-wrap: wrap;
  }
  .table-wrap {
    margin-top: 16px;
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius);
    overflow: auto;
  }
  table {
    width: 100%;
    border-collapse: collapse;
  }
  th,
  td {
    padding: 7px 10px;
    text-align: start;
    white-space: nowrap;
  }
  th {
    color: var(--text-secondary);
    background: var(--surface-subtle);
    border-bottom: 1px solid var(--border-subtle);
  }
  td:nth-child(2) {
    white-space: normal;
  }
  .num {
    text-align: end;
  }
  tbody tr:hover {
    background: var(--hover);
  }
  tbody tr.selected {
    background: var(--accent-subtle);
  }
  .pick {
    display: inline-flex;
    align-items: center;
    gap: 8px;
  }
  .pick input {
    accent-color: var(--accent);
    margin: 0;
  }
  .status {
    color: var(--warning);
  }
  .status.ready {
    color: var(--success);
  }
  .detail {
    margin-top: 12px;
  }
  .detail p {
    margin: 0 0 2px;
    overflow-wrap: anywhere;
  }
</style>
