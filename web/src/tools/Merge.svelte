<script lang="ts">
  // Merge (tab_merge.py): several PDFs, in the order of the list, into one.
  import { onDestroy } from "svelte";
  import { api } from "../lib/bridge";
  import { previewFile } from "../lib/app.svelte";
  import { t } from "../lib/i18n.svelte";
  import { OutputPath } from "../lib/output.svelte";
  import { Feedback, ToolRun } from "../lib/run.svelte";
  import type { FileInfo } from "../lib/types";
  import FeedbackPanel from "../components/Feedback.svelte";
  import FileField from "../components/FileField.svelte";
  import FileList from "../components/FileList.svelte";
  import ProgressFooter from "../components/ProgressFooter.svelte";
  import ToolLayout from "../components/ToolLayout.svelte";

  let files = $state<FileInfo[]>([]);
  let selected = $state(-1);
  const output = new OutputPath("merge");
  const feedback = new Feedback(t("merge_pdf_files"), t("str_drag_drop_hint"));
  const run = new ToolRun(feedback);

  async function append(added: FileInfo[]) {
    const pdfs = added.filter((file) => file.kind === "pdf");
    if (!pdfs.length) return;
    const first = files.length === 0;
    files = [...files, ...pdfs];
    if (first) previewFile(files[0].path);
    if (!output.value.trim()) await output.suggest(files[0].path);
  }

  async function add() {
    await append(await api().pick_files("pdf", true));
  }

  export function drop(dropped: FileInfo[]) {
    void append(dropped);
  }

  function startMerge() {
    void run.start("merge", { files: files.map((file) => file.path), output: output.value.trim() },
                   { askOverwrite: output.ask });
  }

  onDestroy(() => run.dispose());
</script>

<ToolLayout hint={t("hint_merge")}>
  <h2 class="section-title">{t("merge_pdf_files")}</h2>
  <div class="list">
    <FileList bind:files bind:selected label={t("merge_pdf_files")} empty={t("merge_empty_hint")} onadd={add}
              onselect={(file) => previewFile(file.path)} />
  </div>

  <div class="spaced">
    <FileField id="merge-output" label={t("str_output_pdf")} button={t("str_save_as")} bind:value={output.value}
               onbrowse={() => output.browse(files[0]?.path ?? "")} oninput={() => output.typed()} />
  </div>

  <ProgressFooter {run} label={t("merge_btn")} onaction={startMerge} />
  <div class="result"><FeedbackPanel {feedback} /></div>
</ToolLayout>

<style>
  .list {
    margin-top: 14px;
  }
  .spaced {
    margin-top: 18px;
  }
  .result {
    margin-top: 16px;
  }
</style>
