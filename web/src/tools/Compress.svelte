<script lang="ts">
  // Compress (tab_compress.py): one PDF in, a quality profile, one PDF out.
  import { onDestroy, onMount } from "svelte";
  import { api } from "../lib/bridge";
  import { app, previewFile } from "../lib/app.svelte";
  import { t } from "../lib/i18n.svelte";
  import { OutputPath } from "../lib/output.svelte";
  import { Feedback, ToolRun } from "../lib/run.svelte";
  import FeedbackPanel from "../components/Feedback.svelte";
  import FileField from "../components/FileField.svelte";
  import ProgressFooter from "../components/ProgressFooter.svelte";
  import ToolLayout from "../components/ToolLayout.svelte";

  const QUALITIES = ["screen", "ebook", "printer", "prepress"] as const;

  let input = $state("");
  let quality = $state<(typeof QUALITIES)[number]>("ebook");
  const output = new OutputPath("compress");
  const feedback = new Feedback(t("compress_settings"), t("compress_quality_hint"));
  const run = new ToolRun(feedback);

  async function setInput(path: string) {
    input = path;
    previewFile(path);
    await output.suggest(path);
  }

  async function browseInput() {
    const [file] = await api().pick_files("pdf");
    if (file) await setInput(file.path);
  }

  function start() {
    void run.start("compress", { input: input.trim(), output: output.value.trim(), quality },
                   { askOverwrite: output.ask });
  }

  onMount(() => app.acceptDrops("compress", (files) => {
    const pdf = files.find((file) => file.kind === "pdf");
    if (pdf) void setInput(pdf.path);
  }));
  onDestroy(() => run.dispose());
</script>

<ToolLayout hint={t("hint_compress")}>
  <h2 class="section-title">{t("str_file_selection")}</h2>
  <div class="fields">
    <FileField id="compress-input" label={t("str_input_pdf")} button={t("str_browse")} bind:value={input}
               onbrowse={browseInput} oninput={(value) => previewFile(value.trim())} />
    <FileField id="compress-output" label={t("str_output_pdf")} button={t("str_save_as")} bind:value={output.value}
               onbrowse={() => output.browse(input)} oninput={() => output.typed()} />
  </div>

  <fieldset class="panel-card settings">
    <legend class="section-title">{t("compress_settings")}</legend>
    <p class="field-label">{t("compress_quality")}</p>
    {#each QUALITIES as option (option)}
      <label class="check"><input type="radio" name="compress-quality" value={option} bind:group={quality} />
        {t(`quality_${option}`)}</label>
    {/each}
    <p class="hint">{t("compress_quality_hint")}</p>
  </fieldset>

  <ProgressFooter {run} label={t("compress_btn")} onaction={start} />
  <div class="result"><FeedbackPanel {feedback} /></div>
</ToolLayout>

<style>
  .fields {
    margin-top: 18px;
  }
  .settings {
    margin: 22px 0 0;
    min-width: 0;
  }
  legend {
    float: left;
    width: 100%;
    padding: 0;
    margin-bottom: 12px;
  }
  .field-label {
    clear: both;
    margin-bottom: 2px;
  }
  .check {
    display: flex;
    margin-top: 6px;
  }
  .hint {
    margin: 10px 0 0;
  }
  .result {
    margin-top: 16px;
  }
</style>
