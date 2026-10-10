<script lang="ts">
  // The assistant: type a command and press Enter, or hold the button and
  // speak. Ctrl+K focuses the field.
  import { api } from "../lib/bridge";
  import { app } from "../lib/app.svelte";
  import { t } from "../lib/i18n.svelte";
  import Icon from "./Icon.svelte";

  let { input = $bindable() }: { input?: HTMLInputElement } = $props();
  let text = $state("");
  let holding = false;

  const LABELS: Record<string, string> = {
    idle: "voice_idle",
    loading: "voice_loading",
    listening: "voice_listening",
    processing: "voice_processing",
    missing: "voice_model_missing",
  };

  let label = $derived.by(() => {
    if (app.assistant === "heard") {
      const heard = app.assistantHeard;
      return `"${heard.length > 40 ? `${heard.slice(0, 40)}...` : heard}"`;
    }
    return t(LABELS[app.assistant] ?? "voice_idle");
  });

  async function submit(event: SubmitEvent) {
    event.preventDefault();
    const command = text.trim();
    if (!command) return;
    text = "";
    await api().assistant_submit(command);
  }

  function press() {
    if (holding || app.assistant === "loading") return;
    holding = true;
    void api().assistant_press();
  }

  function release() {
    if (!holding) return;
    holding = false;
    void api().assistant_release();
  }

  function key(event: KeyboardEvent, down: boolean) {
    if (event.key !== " " && event.key !== "Enter") return;
    event.preventDefault();
    if (down && !event.repeat) press();
    else if (!down) release();
  }
</script>

<form class="command" onsubmit={submit}>
  <input
    bind:this={input}
    bind:value={text}
    class="small"
    type="text"
    placeholder={t("chat_placeholder")}
    aria-label={t("chat_placeholder")}
    onkeydown={(event) => event.key === "Escape" && input?.blur()}
  />
  <button
    type="button"
    class="voice small-strong"
    class:listening={app.assistant === "listening"}
    disabled={app.assistant === "loading"}
    title={t("voice_hold_hint")}
    onpointerdown={(event) => {
      (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
      press();
    }}
    onpointerup={release}
    onpointercancel={release}
    onkeydown={(event) => key(event, true)}
    onkeyup={(event) => key(event, false)}
  >
    <Icon name="MIC" size={13} />
    <span class="ellipsis">{label}</span>
  </button>
</form>

<style>
  .command {
    display: flex;
    align-items: center;
    width: 322px;
    max-width: 100%;
    padding: 3px 4px;
    background: var(--field);
    border: 1px solid var(--border);
    border-radius: var(--radius);
  }
  .command:hover {
    border-color: var(--border-strong);
  }
  .command:focus-within {
    border-color: var(--accent);
    box-shadow: 0 0 0 2px var(--focus-ring);
  }
  input {
    flex: 1 1 auto;
    min-width: 0;
    border: 0;
    background: transparent;
    padding: 5px 10px;
    color: var(--text);
  }
  input::placeholder {
    color: var(--text-tertiary);
  }
  .voice {
    flex: none;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    max-width: 180px;
    padding: 4px 10px;
    border: 1px solid transparent;
    border-radius: var(--radius-sm);
    background: var(--field);
    color: var(--text-secondary);
    touch-action: none;
  }
  .voice:hover:not(:disabled) {
    background: var(--hover);
    color: var(--text);
  }
  .voice.listening {
    background: var(--danger-bg);
    border-color: var(--danger-border);
    color: var(--danger);
  }
  .voice:disabled {
    color: var(--text-disabled);
  }
</style>
