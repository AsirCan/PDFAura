<script lang="ts">
  // The result panel: the state in words and colour, what happened, and
  // buttons to open the output once there is one.
  import { api } from "../lib/bridge";
  import { t } from "../lib/i18n.svelte";
  import type { Feedback } from "../lib/run.svelte";
  import type { IconName } from "../lib/generated/icons";
  import Icon from "./Icon.svelte";

  let { feedback }: { feedback: Feedback } = $props();
  let panel: HTMLElement | undefined = $state();

  const GLYPHS: Record<string, IconName> = {
    neutral: "INFO", info: "INFO", busy: "SYNC", success: "SUCCESS", warning: "WARNING", danger: "ERROR",
  };

  // A finished job's result must be on screen, not below the fold.
  $effect(() => {
    if (["success", "warning", "danger"].includes(feedback.tone)) {
      panel?.scrollIntoView?.({ block: "nearest", behavior: "smooth" });
    }
  });
</script>

<section class="feedback tone-{feedback.tone}" bind:this={panel} aria-live="polite">
  <p class="badge micro">
    <Icon name={GLYPHS[feedback.tone]} size={12} />
    <span>{feedback.badge}</span>
  </p>
  <p class="title body-strong">{feedback.title}</p>
  <p class="message small selectable">{feedback.message}</p>
  {#if feedback.output}
    <div class="actions">
      <button class="btn btn-secondary btn-small" onclick={() => api().open_path(feedback.output!)}>
        <Icon name="OPEN" size={12} />{t("feedback_open_output")}
      </button>
      <button class="btn btn-ghost btn-small" onclick={() => api().reveal_path(feedback.output!)}>
        <Icon name="FOLDER" size={12} />{t("feedback_open_folder")}
      </button>
    </div>
  {/if}
</section>

<style>
  .feedback {
    background: var(--surface-subtle);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius);
    padding: 12px 14px;
  }
  p {
    margin: 0;
  }
  .badge {
    display: flex;
    align-items: center;
    gap: 6px;
    color: var(--text-secondary);
  }
  .tone-info .badge,
  .tone-busy .badge {
    color: var(--accent-text);
  }
  .tone-success .badge {
    color: var(--success);
  }
  .tone-warning .badge {
    color: var(--warning);
  }
  .tone-danger .badge {
    color: var(--danger);
  }
  .tone-busy .badge :global(.icon) {
    animation: spin 1.2s linear infinite;
  }
  .title {
    margin-top: 8px;
    overflow-wrap: anywhere;
  }
  .message {
    margin-top: 3px;
    color: var(--text-secondary);
    white-space: pre-line;
    overflow-wrap: anywhere;
  }
  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 12px;
  }
  .actions .btn-small {
    font: var(--weight-small-strong) var(--size-small-strong) / 1.2 var(--font-small-strong);
    padding: 5px 12px;
  }
  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .tone-busy .badge :global(.icon) {
      animation: none;
    }
  }
</style>
