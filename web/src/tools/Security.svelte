<script lang="ts">
  // Security: encrypt, decrypt or watermark a PDF.
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
  type Position = "center" | "top-left" | "top-right" | "bottom-left" | "bottom-right" | "tiled";
  const POSITIONS: Position[] = ["center", "top-left", "top-right", "bottom-left", "bottom-right", "tiled"];
  let input = $state("");
  let mode = $state<Mode>("encrypt");
  let password = $state("");
  let confirm = $state("");
  let owner = $state("");
  let allow = $state({ print: true, modify: true, copy: true, annotate: true });
  let watermark = $state("GIZLI");
  let watermarkImage = $state("");
  let opacity = $state(0.3);
  let angle = $state(45);
  let position = $state<Position>("center");
  const output = new OutputPath("security");
  const feedback = new Feedback(() => t("security_op_type"), () => t("security_watermark_text"));
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

  async function browseLogo() {
    const [file] = await api().pick_files("image");
    if (file) watermarkImage = file.path;
  }

  function positionLabel(value: Position) {
    return t(`security_position_${value.replace("-", "_")}`);
  }

  let starting = $state(false);

  async function start() {
    if (starting || run.busy) return;
    starting = true;
    try {
      await run.start("security", {
        input: input.trim(), output: output.value.trim(), mode, password, confirm,
        watermark_text: watermark.trim(), owner_password: owner,
        allow_print: allow.print, allow_modify: allow.modify,
        allow_copy: allow.copy, allow_annotate: allow.annotate,
        watermark_image: watermarkImage.trim(),
        opacity: Number(opacity) || 0.3,
        angle: Number(angle) || 0,
        position,
      }, { output });
    } finally {
      starting = false;
    }
  }

  onMount(() => app.acceptDrops("security", (files) => {
    const pdf = files.find((file) => file.kind === "pdf");
    if (pdf) void setInput(pdf.path);
  }));
  onDestroy(() => {
    if (run.busy) run.cancel();
    run.dispose();
  });
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

      <div class="spaced">
        <FileField id="security-logo" label={t("security_watermark_image")} button={t("str_browse")}
                   bind:value={watermarkImage} onbrowse={browseLogo} />
      </div>

      <div class="row options">
        <div class="grow">
          <label class="field-label" for="security-opacity">{t("security_watermark_opacity")}</label>
          <input id="security-opacity" class="input" type="number" min="0" max="1" step="0.1"
                 bind:value={opacity} />
        </div>
        <div class="grow">
          <label class="field-label" for="security-angle">{t("security_watermark_angle")}</label>
          <input id="security-angle" class="input" type="number" step="15" bind:value={angle} />
        </div>
        <div class="grow">
          <label class="field-label" for="security-position">{t("security_watermark_position")}</label>
          <select id="security-position" class="select" bind:value={position}>
            {#each POSITIONS as value (value)}
              <option value={value}>{positionLabel(value)}</option>
            {/each}
          </select>
        </div>
      </div>
    {:else}
      <label class="field-label" for="security-password">{t("security_password")}</label>
      <input id="security-password" class="input" type="password" autocomplete="new-password" bind:value={password} />
      {#if mode === "encrypt"}
        <!-- Only when encrypting: removing a password needs no confirmation. -->
        <label class="field-label confirm" for="security-confirm">{t("security_password_confirm")}</label>
        <input id="security-confirm" class="input" type="password" autocomplete="new-password" bind:value={confirm} />

        <label class="field-label confirm" for="security-owner">{t("security_owner_password")}</label>
        <input id="security-owner" class="input" type="password" autocomplete="new-password" bind:value={owner} />

        <p class="field-label confirm">{t("security_permissions")}</p>
        <div class="checks">
          <label class="check"><input id="security-allow-print" type="checkbox" bind:checked={allow.print} />{t("security_allow_print")}</label>
          <label class="check"><input id="security-allow-modify" type="checkbox" bind:checked={allow.modify} />{t("security_allow_modify")}</label>
          <label class="check"><input id="security-allow-copy" type="checkbox" bind:checked={allow.copy} />{t("security_allow_copy")}</label>
          <label class="check"><input id="security-allow-annotate" type="checkbox" bind:checked={allow.annotate} />{t("security_allow_annotate")}</label>
        </div>
      {/if}
    {/if}
  </div>

  <div class="spaced">
    <FileField id="security-output" label={t("str_output_pdf")} button={t("str_save_as")} bind:value={output.value}
               onbrowse={() => output.browse(input, mode)} oninput={() => output.typed()} />
  </div>

  <ProgressFooter {run} label={t("str_apply")} onaction={start} disabled={starting} />
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
  .options {
    align-items: flex-start;
    margin-top: 18px;
  }
  .checks {
    display: flex;
    flex-wrap: wrap;
    gap: 0 22px;
  }
  .result {
    margin-top: 16px;
  }
</style>
