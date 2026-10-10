<script lang="ts">
  // Edit pages: delete, rotate or reorder pages of a PDF.
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
  import Segmented from "../components/Segmented.svelte";
  import ToolLayout from "../components/ToolLayout.svelte";

  type Mode = "delete" | "rotate" | "reorder";
  let input = $state("");
  let info = $state("");
  let mode = $state<Mode>("delete");
  let deletePages = $state("");
  let rotatePages = $state("");
  let angle = $state("90");
  let order = $state("");
  const output = new OutputPath("edit");
  const feedback = new Feedback(() => t("edit_operation"), () => t("edit_delete_hint"));
  const run = new ToolRun(feedback);

  async function setInput(path: string) {
    input = path;
    previewFile(path);
    const count = await pageCount(path);
    info = count.pages !== undefined ? t("edit_total_pages", { count: count.pages })
      : count.error ? `${t("str_error")}: ${count.error}` : "";
    await output.suggest(path);
  }

  async function browse() {
    const [file] = await api().pick_files("pdf");
    if (file) await setInput(file.path);
  }

  export function drop(files: FileInfo[]) {
    const pdf = files.find((file) => file.kind === "pdf");
    if (pdf) void setInput(pdf.path);
  }

  function startEdit() {
    void run.start("edit", {
      input: input.trim(), output: output.value.trim(), mode, delete_pages: deletePages.trim(),
      rotate_pages: rotatePages.trim(), angle, order: order.trim(),
    }, { askOverwrite: output.ask });
  }

  onDestroy(() => run.dispose());
</script>

<ToolLayout hint={t("hint_edit")}>
  <FileField id="edit-input" label={t("str_input_pdf")} button={t("str_browse")} bind:value={input}
             onbrowse={browse} oninput={(value) => previewFile(value.trim())} />
  {#if info}<p class="page-info small-strong">{info}</p>{/if}

  <p class="field-label spaced">{t("edit_operation")}</p>
  <Segmented label={t("edit_operation")} bind:value={mode} options={[
    { value: "delete", label: t("edit_mode_delete") },
    { value: "rotate", label: t("edit_mode_rotate") },
    { value: "reorder", label: t("edit_mode_reorder") },
  ]} />

  <div class="panel-card mode">
    {#if mode === "delete"}
      <label class="field-label" for="edit-delete">{t("edit_pages_to_delete")}</label>
      <input id="edit-delete" class="input" bind:value={deletePages} />
      <p class="hint">{t("edit_delete_hint")}</p>
    {:else if mode === "rotate"}
      <label class="field-label" for="edit-rotate">{t("edit_pages_to_rotate")}</label>
      <input id="edit-rotate" class="input" bind:value={rotatePages} />
      <p class="hint">{t("edit_rotate_hint")}</p>
      <div class="row angle">
        <label class="field-label inline" for="edit-angle">{t("edit_angle")}</label>
        <span class="select-wrap">
          <select id="edit-angle" class="select" bind:value={angle}>
            <option value="90">90</option><option value="180">180</option><option value="270">270</option>
          </select>
        </span>
        <span class="hint">{t("edit_angle_hint")}</span>
      </div>
    {:else}
      <label class="field-label" for="edit-order">{t("edit_new_order")}</label>
      <input id="edit-order" class="input" bind:value={order} />
      <p class="hint">{t("edit_order_hint")}</p>
    {/if}
  </div>

  <div class="spaced">
    <FileField id="edit-output" label={t("str_output_pdf")} button={t("str_save_as")} bind:value={output.value}
               onbrowse={() => output.browse(input)} oninput={() => output.typed()} />
  </div>

  <ProgressFooter {run} label={t("str_apply")} onaction={startEdit} />
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
  .mode {
    margin-top: 18px;
  }
  .hint {
    margin: 8px 0 0;
  }
  .angle {
    margin-top: 10px;
  }
  .angle .hint {
    margin: 0;
  }
  .field-label.inline {
    margin: 0;
  }
  .result {
    margin-top: 16px;
  }
</style>
