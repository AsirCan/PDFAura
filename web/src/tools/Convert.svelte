<script lang="ts">
  // Convert (tab_convert.py): seven conversions, each keeping its own files.
  import { onDestroy, onMount } from "svelte";
  import { api } from "../lib/bridge";
  import { app, previewFile } from "../lib/app.svelte";
  import { t } from "../lib/i18n.svelte";
  import { OutputPath } from "../lib/output.svelte";
  import { Feedback, ToolRun } from "../lib/run.svelte";
  import type { FileInfo } from "../lib/types";
  import FeedbackPanel from "../components/Feedback.svelte";
  import FileField from "../components/FileField.svelte";
  import FileList from "../components/FileList.svelte";
  import ProgressFooter from "../components/ProgressFooter.svelte";
  import Segmented from "../components/Segmented.svelte";
  import ToolLayout from "../components/ToolLayout.svelte";

  type Mode = "pdf2img" | "img2pdf" | "pdf2word" | "word2pdf" | "ppt2pdf" | "excel2pdf" | "pdf2txt";
  type Single = Exclude<Mode, "img2pdf">;
  const MODES: Mode[] = ["pdf2img", "img2pdf", "pdf2word", "word2pdf", "ppt2pdf", "excel2pdf", "pdf2txt"];
  // What each one-file conversion takes and gives: dialog kinds and labels.
  const SINGLE: Record<Single, { input: string; inputLabel: string; output: string; outputLabel: string }> = {
    pdf2img: { input: "pdf", inputLabel: "str_input_pdf", output: "folder", outputLabel: "str_output_folder" },
    pdf2word: { input: "pdf", inputLabel: "str_input_pdf", output: "docx", outputLabel: "convert_output_word" },
    word2pdf: { input: "word", inputLabel: "convert_input_word", output: "pdf", outputLabel: "str_output_pdf" },
    ppt2pdf: { input: "powerpoint", inputLabel: "convert_input_ppt", output: "pdf", outputLabel: "str_output_pdf" },
    excel2pdf: { input: "excel", inputLabel: "convert_input_excel", output: "pdf", outputLabel: "str_output_pdf" },
    pdf2txt: { input: "pdf", inputLabel: "str_input_pdf", output: "text", outputLabel: "convert_output_txt" },
  };

  let mode = $state<Mode>("pdf2img");
  const inputs = $state<Record<Single, string>>({
    pdf2img: "", pdf2word: "", word2pdf: "", ppt2pdf: "", excel2pdf: "", pdf2txt: "",
  });
  const outputs = Object.fromEntries(MODES.map((key) => [key, new OutputPath("convert",
    key === "img2pdf" ? "pdf" : SINGLE[key as Single].output)])) as Record<Mode, OutputPath>;
  let dpi = $state("300");
  let format = $state("PNG");
  let images = $state<FileInfo[]>([]);
  let selectedImage = $state(-1);
  let pageSize = $state("original");
  const feedback = new Feedback(t("convert_type"), t("convert_running", { mode: t("convert_pdf2img") }));
  const run = new ToolRun(feedback);

  let single = $derived(mode === "img2pdf" ? null : SINGLE[mode]);

  function switchMode(next: Mode) {
    feedback.info(t("convert_type"), t("convert_running", { mode: t(`convert_${next}`) }));
    if (next === "img2pdf" || SINGLE[next as Single].input !== "pdf") previewFile(null);
    else previewFile(inputs[next as Single] || null);
  }

  async function setInput(target: Single, path: string) {
    inputs[target] = path;
    if (SINGLE[target].input === "pdf") previewFile(path);
    await outputs[target].suggest(path, target);
  }

  async function browseInput() {
    if (!single) return;
    const [file] = await api().pick_files(single.input);
    if (file) await setInput(mode as Single, file.path);
  }

  function browseOutput() {
    const output = outputs[mode];
    if (mode === "pdf2img") void output.browseFolder();
    else if (mode === "img2pdf") void output.browse(images[0]?.path ?? "", mode);
    else void output.browse(inputs[mode as Single], mode);
  }

  async function addImages(added: FileInfo[]) {
    const pictures = added.filter((file) => file.kind === "image");
    if (!pictures.length) return false;
    images = [...images, ...pictures];
    if (!outputs.img2pdf.value.trim()) await outputs.img2pdf.suggest(images[0].path, "img2pdf");
    return true;
  }

  async function pickImages() {
    await addImages(await api().pick_files("image", true));
  }

  const ACCEPTS: Record<Single, string> = {
    pdf2img: "pdf", pdf2word: "pdf", pdf2txt: "pdf", word2pdf: "word", ppt2pdf: "powerpoint", excel2pdf: "excel",
  };

  async function drop(files: FileInfo[]) {
    for (const file of files) {
      const fits = mode === "img2pdf" ? file.kind === "image" : file.kind === ACCEPTS[mode as Single];
      if (!fits) {
        // A file that does not suit the mode used to be ignored without a word.
        feedback.info(t("convert_dialog_pdf"), t("convert_drop_mismatch", { name: file.name }));
        continue;
      }
      if (mode === "img2pdf") await addImages([file]);
      else await setInput(mode as Single, file.path);
    }
  }

  function start() {
    const params: Record<string, unknown> = { mode };
    if (mode === "pdf2img") {
      Object.assign(params, { input: inputs.pdf2img.trim(), output: outputs.pdf2img.value.trim(), dpi,
                              fmt: format });
    } else if (mode === "img2pdf") {
      Object.assign(params, { images: images.map((file) => file.path), output: outputs.img2pdf.value.trim(),
                              page_size: pageSize });
    } else {
      Object.assign(params, { input: inputs[mode].trim(), output: outputs[mode].value.trim() });
    }
    void run.start("convert", params, { askOverwrite: outputs[mode].ask });
  }

  onMount(() => app.acceptDrops("convert", (files) => void drop(files)));
  onDestroy(() => run.dispose());
</script>

<ToolLayout hint={t("hint_convert")}>
  <p class="field-label">{t("convert_type")}</p>
  <Segmented label={t("convert_type")} bind:value={mode} onchange={switchMode}
             options={MODES.map((value) => ({ value, label: t(`convert_${value}`) }))} />

  <div class="panel-card mode">
    {#if single}
      {#key mode}
        <FileField id="convert-input" label={t(single.inputLabel)} button={t("str_browse")}
                   bind:value={inputs[mode as Single]} onbrowse={browseInput}
                   oninput={(value) => single?.input === "pdf" && previewFile(value.trim())} />
        <div class="spaced">
          <FileField id="convert-output" label={t(single.outputLabel)}
                     button={t(mode === "pdf2img" ? "str_browse" : "str_save")}
                     bind:value={outputs[mode].value} onbrowse={browseOutput} oninput={() => outputs[mode].typed()} />
        </div>
      {/key}
      {#if mode === "pdf2img"}
        <div class="row options">
          <label class="field-label inline" for="convert-dpi">DPI</label>
          <span class="select-wrap">
            <select id="convert-dpi" class="select" bind:value={dpi}>
              {#each ["72", "150", "300", "600"] as value (value)}<option {value}>{value}</option>{/each}
            </select>
          </span>
          <label class="field-label inline gap" for="convert-format">Format</label>
          <span class="select-wrap">
            <select id="convert-format" class="select" bind:value={format}>
              <option value="PNG">PNG</option><option value="JPEG">JPEG</option>
            </select>
          </span>
        </div>
      {/if}
    {:else}
      <p class="field-label">{t("convert_image_files")}</p>
      <FileList bind:files={images} bind:selected={selectedImage} label={t("convert_image_files")}
                empty={t("convert_images_empty_hint")} onadd={pickImages} />
      <div class="spaced">
        <FileField id="convert-images-output" label={t("str_output_pdf")} button={t("str_save")}
                   bind:value={outputs.img2pdf.value} onbrowse={browseOutput} oninput={() => outputs.img2pdf.typed()} />
      </div>
      <div class="row options">
        <label class="field-label inline" for="convert-size">{t("convert_page_size")}</label>
        <span class="select-wrap">
          <select id="convert-size" class="select" bind:value={pageSize}>
            <option value="original">{t("convert_original")}</option>
            <option value="A4">A4</option>
            <option value="Letter">Letter</option>
          </select>
        </span>
      </div>
    {/if}
  </div>

  <ProgressFooter {run} label={t("convert_btn")} onaction={start} />
  <div class="result"><FeedbackPanel {feedback} /></div>
</ToolLayout>

<style>
  .mode {
    margin-top: 18px;
  }
  .spaced {
    margin-top: 14px;
  }
  .options {
    margin-top: 14px;
  }
  .field-label.inline {
    margin: 0;
  }
  .gap {
    margin-inline-start: 8px !important;
  }
  .result {
    margin-top: 16px;
  }
</style>
