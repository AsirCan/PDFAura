<script lang="ts">
  // Security (tab_security.py): encrypt, decrypt or watermark a PDF.
  import { onDestroy, onMount } from "svelte";
  import { api } from "../lib/bridge";
  import { app, previewFile } from "../lib/app.svelte";
  import { t } from "../lib/i18n.svelte";
  import { OutputPath } from "../lib/output.svelte";
  import { Feedback, ToolRun } from "../lib/run.svelte";
  import FeedbackPanel from "../components/Feedback.svelte";
  import FileField from "../components/FileField.svelte";
  import ProgressFooter from "../components/ProgressFooter.svelte";
  import Segmented from "../components/Segmented.svelte";
  import ToolLayout from "../components/ToolLayout.svelte";

  type Mode = "encrypt" | "decrypt" | "watermark";
  let input = $state("");
  let mode = $state<Mode>("encrypt");
  let password = $state("");
  let confirm = $state("");
  let watermark = $state("GIZLI");
  const output = new OutputPath("security");
  const feedback = new Feedback(t("security_op_type"), t("security_watermark_text"));
  const run = new ToolRun(feedback);

  async function setInput(path: string) {
    input = path;
    previewFile(path);
    await output.suggest(path, mode);
  }

  async function browse() {
    const [file] = await api().pick_files("pdf");
    if (file) await setInput(file.path);
  }

  function start() {
    void run.start("security", {
      input: input.trim(), output: output.value.trim(), mode, password, confirm, watermark_text: watermark.trim(),
    }, { askOverwrite: output.ask });
  }

  onMount(() => app.acceptDrops("security", (files) => {
    const pdf = files.find((file) => file.kind === "pdf");
    if (pdf) void setInput(pdf.path);
  }));
  onDestroy(() => run.dispose());
</script>

<ToolLayout hint={t("hint_security")}>
  <FileField id="security-input" label={t("str_input_pdf")} button={t("str_browse")} bind:value={input}
             onbrowse={browse} oninput={(value) => previewFile(value.trim())} />

  <p class="field-label spaced">{t("security_op_type")}</p>
  <Segmented label={t("security_op_type")} bind:value={mode}
             onchange={(next) => input && output.suggest(input, next)} options={[
    { value: "encrypt", label: t("security_encrypt") },
    { value: "decrypt", label: t("security_decrypt") },
    { value: "watermark", label: t("security_watermark") },
  ]} />

  <div class="panel-card mode">
    {#if mode === "watermark"}
      <label class="field-label" for="security-watermark">{t("security_watermark_text")}</label>
      <input id="security-watermark" class="input" bind:value={watermark} />
    {:else}
      <label class="field-label" for="security-password">{t("security_password")}</label>
      <input id="security-password" class="input" type="password" autocomplete="new-password" bind:value={password} />
      {#if mode === "encrypt"}
        <!-- Only when encrypting: removing a password needs no confirmation. -->
        <label class="field-label confirm" for="security-confirm">{t("security_password_confirm")}</label>
        <input id="security-confirm" class="input" type="password" autocomplete="new-password" bind:value={confirm} />
      {/if}
    {/if}
  </div>

  <div class="spaced">
    <FileField id="security-output" label={t("str_output_pdf")} button={t("str_save_as")} bind:value={output.value}
               onbrowse={() => output.browse(input, mode)} oninput={() => output.typed()} />
  </div>

  <ProgressFooter {run} label={t("str_apply")} onaction={start} />
  <div class="result"><FeedbackPanel {feedback} /></div>
</ToolLayout>

<style>
  .spaced {
    margin-top: 18px;
  }
  .mode {
    margin-top: 18px;
  }
  .confirm {
    margin-top: 12px;
  }
  .result {
    margin-top: 16px;
  }
</style>
