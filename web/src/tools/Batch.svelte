<script lang="ts">
  // Batch (tab_batch.py): compress, convert or rename every file in a
  // folder, with a log that shows each file as it is done.
  import { onDestroy, onMount, tick } from "svelte";
  import { api } from "../lib/bridge";
  import { app } from "../lib/app.svelte";
  import { t } from "../lib/i18n.svelte";
  import { Feedback, ToolRun } from "../lib/run.svelte";
  import FeedbackPanel from "../components/Feedback.svelte";
  import FileField from "../components/FileField.svelte";
  import ProgressFooter from "../components/ProgressFooter.svelte";
  import Segmented from "../components/Segmented.svelte";
  import ToolLayout from "../components/ToolLayout.svelte";

  type Mode = "compress" | "convert" | "rename";
  const MODE_LABELS: Record<Mode, string> = { compress: "batch_compress", convert: "batch_convert",
                                              rename: "batch_rename" };
  let inputDir = $state("");
  let outputDir = $state("");
  let mode = $state<Mode>("compress");
  let quality = $state("screen");
  let convertMode = $state("pdf2img");
  let renameRule = $state(t("batch_rename_default"));
  let log = $state<string[]>([]);
  let logBox: HTMLElement | undefined = $state();
  const feedback = new Feedback(t("batch_main_type"), t("batch_rename_hint"));
  const run: ToolRun = new ToolRun(feedback, {
    progress: (current, total, message) => {
      const pct = Math.floor((current / Math.max(1, total)) * 100);
      run.percent = pct;
      run.note = t("batch_progress", { pct, cur: current, total });
      if (message) append(message);
    },
    done: (outcome) => {
      const counts = outcome.details as { succeeded: number; failed: number };
      append(t("batch_log_ended"));
      append(t("batch_success_count", { succ: counts.succeeded, errs: counts.failed }));
    },
    cancelled: () => append(`\n--- ${t("perf_cancelled")} ---`),
  });

  async function append(line: string) {
    log = [...log, line];
    await tick();
    logBox?.scrollTo({ top: logBox.scrollHeight });
  }

  async function pick(which: "input" | "output") {
    const folder = await api().pick_folder(which === "input" ? inputDir : outputDir);
    if (!folder) return;
    if (which === "input") inputDir = folder.path;
    else outputDir = folder.path;
  }

  async function start() {
    const started = await run.start("batch", {
      mode, input_dir: inputDir.trim(), output_dir: outputDir.trim(), quality, convert_mode: convertMode,
      rename_rule: renameRule,
    });
    if (started) {
      log = [];
      void append(t("batch_log_started", { path: inputDir.trim() }));
    }
  }

  onMount(() => app.acceptDrops("batch", (files) => {
    const folder = files.find((file) => file.is_dir);
    if (!folder) return;
    if (!inputDir.trim()) inputDir = folder.path;
    else if (!outputDir.trim()) outputDir = folder.path;
  }));
  onDestroy(() => run.dispose());
</script>

<ToolLayout hint={t("hint_batch")}>
  <FileField id="batch-input" label={t("str_input_folder")} button={t("str_select_dir")} bind:value={inputDir}
             onbrowse={() => pick("input")} />

  <p class="field-label spaced">{t("batch_main_type")}</p>
  <Segmented label={t("batch_main_type")} bind:value={mode}
             onchange={(next) => feedback.info(t("batch_main_type"), t(MODE_LABELS[next]))} options={[
    { value: "compress", label: t("batch_compress") },
    { value: "convert", label: t("batch_convert") },
    { value: "rename", label: t("batch_rename") },
  ]} />

  <div class="panel-card mode">
    {#if mode === "compress"}
      <label class="field-label" for="batch-quality">{t("batch_compress_quality")}</label>
      <span class="select-wrap">
        <select id="batch-quality" class="select" bind:value={quality}>
          {#each ["screen", "ebook", "printer", "prepress"] as option (option)}
            <option value={option}>{t(`quality_${option}`)}</option>
          {/each}
        </select>
      </span>
    {:else if mode === "convert"}
      <label class="check"><input type="radio" name="batch-convert" value="pdf2img" bind:group={convertMode} />
        {t("batch_radio_pdf2img")}</label>
      <label class="check"><input type="radio" name="batch-convert" value="img2pdf" bind:group={convertMode} />
        {t("batch_radio_img2pdf")}</label>
    {:else}
      <label class="field-label" for="batch-rule">{t("batch_rename_rule")}</label>
      <input id="batch-rule" class="input" dir="auto" bind:value={renameRule} />
      <p class="hint">{t("batch_rename_hint")}</p>
    {/if}
  </div>

  <div class="spaced">
    <FileField id="batch-output" label={t("str_output_folder_label")} button={t("str_select_dir")}
               bind:value={outputDir} onbrowse={() => pick("output")} />
  </div>

  <ProgressFooter {run} label={t("batch_start_btn")} onaction={start} />

  <section class="panel-card log-card">
    <h2 class="section-title">{t("batch_log_title")}</h2>
    <pre class="log mono selectable" bind:this={logBox} aria-live="polite">{log.join("\n")}</pre>
  </section>

  <div class="result"><FeedbackPanel {feedback} /></div>
</ToolLayout>

<style>
  .spaced {
    margin-top: 18px;
  }
  .mode {
    margin-top: 18px;
  }
  .check {
    display: flex;
  }
  .check + .check {
    margin-top: 8px;
  }
  .hint {
    margin: 10px 0 0;
  }
  .log-card {
    margin-top: 18px;
    padding: 14px;
  }
  .log {
    margin: 10px 0 0;
    min-height: 160px;
    max-height: 260px;
    overflow: auto;
    padding: 8px 10px;
    background: var(--surface-subtle);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }
  .result {
    margin-top: 16px;
  }
</style>
