<script lang="ts">
  // Advanced (tab_advanced.py): full preview, OCR to text, metadata and a
  // visual signature stamp.
  import { onDestroy, onMount } from "svelte";
  import { api, on } from "../lib/bridge";
  import { app, previewFile } from "../lib/app.svelte";
  import { t } from "../lib/i18n.svelte";
  import { OutputPath } from "../lib/output.svelte";
  import { Feedback, ToolRun } from "../lib/run.svelte";
  import FeedbackPanel from "../components/Feedback.svelte";
  import FileField from "../components/FileField.svelte";
  import ProgressFooter from "../components/ProgressFooter.svelte";
  import Segmented from "../components/Segmented.svelte";
  import ToolLayout from "../components/ToolLayout.svelte";

  type Mode = "preview" | "ocr" | "metadata" | "signature";
  const MODE_LABELS: Record<Mode, string> = {
    preview: "adv_preview", ocr: "adv_ocr", metadata: "adv_metadata", signature: "adv_signature",
  };
  let input = $state("");
  let mode = $state<Mode>("preview");
  // Until the fields hold this document's metadata, an empty field means
  // "leave alone", not "erase" (metadata_fields in src/app/tools.py).
  let meta = $state({ title: "", author: "", subject: "", creator: "" });
  let loadedFor = $state<string | null>(null);
  let clean = $state(false);
  let signature = $state({ image: "", page: "1", x: "100", y: "100", scale: "1.0" });
  let tesseract = $state<boolean | null>(null);
  let installing = $state(false);
  const output = new OutputPath("advanced", "pdf");
  const feedback = new Feedback(t("adv_operation"), t("adv_preview_hint"));
  const run = new ToolRun(feedback);

  async function setInput(path: string) {
    input = path;
    previewFile(path);
    await loadMetadata(true);
  }

  async function browse() {
    const [file] = await api().pick_files("pdf");
    if (file) await setInput(file.path);
  }

  async function loadMetadata(quiet = false) {
    const path = input.trim();
    const result = await api().read_metadata(path);
    if (result.error) {
      loadedFor = null;
      if (!quiet) {
        feedback.error(t("str_error"), result.error === "missing" ? t("err_select_valid_file")
          : `${t("err_metadata_read")} ${result.error}`);
      }
      return;
    }
    meta = { title: result.title, author: result.author, subject: result.subject, creator: result.creator };
    loadedFor = path;
    if (!quiet) feedback.info(t("str_info"), t("adv_meta_read_ok"));
  }

  async function switchMode(next: Mode) {
    feedback.info(t("adv_operation"), t(MODE_LABELS[next]));
    // The save dialog offers .txt for OCR and .pdf otherwise.
    output.kind = next === "ocr" ? "text" : "pdf";
    if (next === "ocr") tesseract = await api().tesseract_available();
  }

  async function pickSignature() {
    const [file] = await api().pick_files("image");
    if (file) signature.image = file.path;
  }

  function browseOutput() {
    // Advanced has no suggested name (as in Tk): the dialog starts empty.
    void output.browse();
  }

  function start() {
    const path = input.trim();
    if (mode === "preview") {
      if (!path) {
        feedback.error(t("str_error"), t("err_select_valid_file"));
        return;
      }
      app.viewer = path;
      feedback.info(t("adv_preview"), t("viewer_title"));
      return;
    }
    const params: Record<string, unknown> = { input: path, output: output.value.trim(), mode };
    if (mode === "metadata") {
      const keep = !clean && loadedFor === path;
      params.metadata = {
        clean, title: keep ? meta.title : null, author: keep ? meta.author : null,
        subject: keep ? meta.subject : null, creator: keep ? meta.creator : null,
      };
    } else if (mode === "signature") {
      params.signature = { ...signature };
    }
    void run.start("advanced", params, { askOverwrite: output.ask });
  }

  const stop = on("tesseract", (event) => {
    installing = false;
    if (event.ok) {
      tesseract = true;
      feedback.success(t("adv_tess_install_title"), t("adv_tess_install_ok"));
    } else {
      feedback.error(t("str_error"), event.message);
    }
  });

  onMount(() => app.acceptDrops("advanced", (files) => {
    const pdf = files.find((file) => file.kind === "pdf");
    if (pdf) void setInput(pdf.path);
  }));
  onDestroy(() => {
    stop();
    run.dispose();
  });
</script>

<ToolLayout hint={t("hint_advanced")}>
  <FileField id="advanced-input" label={t("str_input_pdf")} button={t("str_select")} bind:value={input}
             onbrowse={browse} oninput={(value) => previewFile(value.trim())} />

  <p class="field-label spaced">{t("adv_operation")}</p>
  <Segmented label={t("adv_operation")} bind:value={mode} onchange={switchMode} options={[
    { value: "preview", label: t("adv_preview") },
    { value: "ocr", label: t("adv_ocr") },
    { value: "metadata", label: t("adv_metadata") },
    { value: "signature", label: t("adv_signature") },
  ]} />

  <div class="panel-card mode">
    {#if mode === "preview"}
      <p class="hint">{t("adv_preview_hint")}</p>
    {:else if mode === "ocr"}
      <p class="hint">{t("adv_ocr_hint")}</p>
      {#if tesseract !== null}
        <p class="section-title status">{t(tesseract ? "adv_tess_installed" : "adv_tess_not_installed")}</p>
        {#if !tesseract}
          <button class="btn btn-secondary install" disabled={installing}
                  onclick={() => { installing = true; void api().install_tesseract(); }}>
            {t(installing ? "adv_tess_installing" : "adv_tess_install_btn")}
          </button>
        {/if}
      {/if}
    {:else if mode === "metadata"}
      <button class="btn btn-secondary" onclick={() => loadMetadata()}>{t("adv_read_meta_btn")}</button>
      <div class="grid">
        <label class="field-label" for="meta-title">{t("adv_meta_title")}</label>
        <input id="meta-title" class="input" dir="auto" bind:value={meta.title} />
        <label class="field-label" for="meta-author">{t("adv_meta_author")}</label>
        <input id="meta-author" class="input" dir="auto" bind:value={meta.author} />
        <label class="field-label" for="meta-subject">{t("adv_meta_subject")}</label>
        <input id="meta-subject" class="input" dir="auto" bind:value={meta.subject} />
        <label class="field-label" for="meta-creator">{t("adv_meta_creator")}</label>
        <input id="meta-creator" class="input" dir="auto" bind:value={meta.creator} />
      </div>
      <label class="check clean"><input type="checkbox" bind:checked={clean} />{t("adv_meta_clean")}</label>
    {:else}
      <div class="grid">
        <label class="field-label" for="sig-image">{t("adv_sig_image")}</label>
        <div class="row">
          <input id="sig-image" class="input grow" dir="auto" bind:value={signature.image} />
          <button class="btn btn-secondary" onclick={pickSignature}>{t("adv_sig_choose")}</button>
        </div>
        <label class="field-label" for="sig-page">{t("adv_sig_page")}</label>
        <input id="sig-page" class="input short" bind:value={signature.page} />
        <label class="field-label" for="sig-x">{t("adv_sig_x")}</label>
        <input id="sig-x" class="input short" bind:value={signature.x} />
        <label class="field-label" for="sig-y">{t("adv_sig_y")}</label>
        <input id="sig-y" class="input short" bind:value={signature.y} />
        <label class="field-label" for="sig-scale">{t("adv_sig_scale")}</label>
        <input id="sig-scale" class="input short" bind:value={signature.scale} />
      </div>
    {/if}
  </div>

  {#if mode !== "preview"}
    <div class="spaced">
      <FileField id="advanced-output" label={t("str_output_dir_file")} button={t("str_save_as")}
                 bind:value={output.value} onbrowse={browseOutput} oninput={() => output.typed()} />
    </div>
  {/if}

  <ProgressFooter {run} label={t("str_start")} onaction={start} />
  <div class="result"><FeedbackPanel {feedback} /></div>
</ToolLayout>

<style>
  .spaced {
    margin-top: 18px;
  }
  .mode {
    margin-top: 18px;
  }
  .hint {
    margin: 0;
  }
  .status {
    margin-top: 12px;
  }
  .install {
    margin-top: 10px;
  }
  .grid {
    display: grid;
    grid-template-columns: max-content minmax(0, 1fr);
    align-items: center;
    gap: 10px 12px;
    margin-top: 10px;
  }
  .grid .field-label {
    margin: 0;
  }
  .short {
    max-width: 180px;
  }
  .clean {
    display: flex;
    margin-top: 12px;
  }
  .result {
    margin-top: 16px;
  }
</style>
