<script lang="ts">
  // Split (tab_split.py): one page range of a PDF into a new PDF.
  import { onDestroy } from "svelte";
  import { api } from "../lib/bridge";
  import { previewFile } from "../lib/app.svelte";
  import { t } from "../lib/i18n.svelte";
  import { OutputPath, pageCount } from "../lib/output.svelte";
  import { Feedback, ToolRun } from "../lib/run.svelte";
  import type { FileInfo } from "../lib/types";
  import FeedbackPanel from "../components/Feedback.svelte";
  import FileField from "../components/FileField.svelte";
  import ProgressFooter from "../components/ProgressFooter.svelte";
  import ToolLayout from "../components/ToolLayout.svelte";

  let input = $state("");
  let start = $state(1);
  let end = $state<number | null>(null);
  let info = $state("");
  const output = new OutputPath("split");
  const feedback = new Feedback(() => t("split_page_range"),
                                () => t("output_action_hint", { action: t("split_btn") }));
  const run = new ToolRun(feedback);

  async function setInput(path: string) {
    input = path;
    previewFile(path);
    const count = await pageCount(path);
    if (count.pages !== undefined) {
      info = t("split_total_pages", { count: count.pages });
      start = 1;
      end = count.pages;
    } else {
      info = count.error ? `${t("split_page_read_err")}${count.error}` : "";
    }
    await suggest();
  }

  async function suggest() {
    if (input && start && end) await output.suggest(input, null, start, end);
  }

  async function browse() {
    const [file] = await api().pick_files("pdf");
    if (file) await setInput(file.path);
  }

  export function drop(files: FileInfo[]) {
    const pdf = files.find((file) => file.kind === "pdf");
    if (pdf) void setInput(pdf.path);
  }

  function startSplit() {
    void run.start("split", { input: input.trim(), output: output.value.trim(), start: String(start ?? ""),
                              end: String(end ?? "") }, { askOverwrite: output.ask });
  }

  onDestroy(() => run.dispose());
</script>

<ToolLayout hint={t("hint_split")}>
  <FileField id="split-input" label={t("str_input_pdf")} button={t("str_browse")} bind:value={input}
             onbrowse={browse} oninput={(value) => previewFile(value.trim())} />
  {#if info}<p class="page-info small-strong">{info}</p>{/if}

  <div class="spaced">
    <FileField id="split-output" label={t("str_output_pdf")} button={t("str_save_as")} bind:value={output.value}
               onbrowse={() => output.browse(input, null, start, end)} oninput={() => output.typed()} />
    <p class="hint">{t("output_action_hint", { action: t("split_btn") })}</p>
  </div>

  <fieldset class="panel-card range">
    <legend class="section-title">{t("split_page_range")}</legend>
    <div class="row pages">
      <label class="stack">
        <span class="field-label">{t("split_start")}</span>
        <input class="input number" type="number" min="1" bind:value={start} oninput={suggest} />
      </label>
      <span class="title dash">–</span>
      <label class="stack">
        <span class="field-label">{t("split_end")}</span>
        <input class="input number" type="number" min="1" bind:value={end} oninput={suggest} />
      </label>
    </div>
    <p class="hint">{t("split_hint")}</p>
  </fieldset>

  <ProgressFooter {run} label={t("split_btn")} onaction={startSplit} />
  <div class="result"><FeedbackPanel {feedback} /></div>
</ToolLayout>

<style>
  .page-info {
    margin: 8px 0 0;
    color: var(--accent-text);
  }
  .spaced {
    margin-top: 18px;
  }
  .hint {
    margin: 8px 0 0;
  }
  .range {
    margin: 22px 0 0;
    min-width: 0;
  }
  legend {
    float: left;
    width: 100%;
    padding: 0;
  }
  .pages {
    clear: both;
    align-items: flex-end;
    padding-top: 14px;
  }
  .number {
    width: 120px;
  }
  .dash {
    padding: 0 4px 6px;
  }
  .result {
    margin-top: 16px;
  }
</style>
