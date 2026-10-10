<script lang="ts">
  // A tool's action row: the main button, then progress and Cancel while a
  // job runs (ProgressFooter in helpers.py). ``working`` is other work the
  // tool waits for (the scanner's corner detection): a bar that only moves.
  import { t } from "../lib/i18n.svelte";
  import type { ToolRun } from "../lib/run.svelte";

  let { run, label, onaction, disabled = false, working = null }:
    { run: ToolRun; label: string; onaction: () => void; disabled?: boolean; working?: string | null } = $props();
</script>

<div class="footer">
  <hr class="divider" />
  <div class="row">
    <button class="btn btn-primary" disabled={run.busy || disabled} onclick={onaction}>{label}</button>
    {#if run.busy && run.cancellable}
      <button class="btn btn-secondary" disabled={run.cancelling} onclick={() => run.cancel()}>
        {t(run.cancelling ? "perf_cancelling" : "perf_cancel")}
      </button>
    {/if}
    {#if working && !run.busy}
      <div class="status grow">
        <div class="bar waiting" role="progressbar" aria-label={working}><span></span></div>
        <p class="small faint ellipsis">{working}</p>
      </div>
    {:else if run.busy || run.finished}
      <div class="status grow">
        <div
          class="bar"
          class:done={run.finished}
          role="progressbar"
          aria-valuemin="0"
          aria-valuemax="100"
          aria-valuenow={run.percent}
        >
          <span style:width="{run.percent}%"></span>
        </div>
        <p class="small faint ellipsis">{run.note}</p>
      </div>
    {/if}
  </div>
</div>

<style>
  .footer {
    margin-top: 24px;
  }
  .divider {
    margin-bottom: 16px;
  }
  .status {
    padding-inline-start: 6px;
  }
  .bar {
    height: 6px;
    border-radius: 3px;
    background: var(--sunken);
    overflow: hidden;
    max-width: 320px;
  }
  .bar span {
    display: block;
    height: 100%;
    background: var(--accent);
    border-radius: 3px;
    transition: width 120ms linear;
  }
  .bar.done span {
    background: var(--success);
  }
  .bar.waiting span {
    width: 30%;
    animation: wait 1.1s ease-in-out infinite alternate;
  }
  @keyframes wait {
    from {
      margin-inline-start: 0;
    }
    to {
      margin-inline-start: 70%;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .bar.waiting span {
      animation: none;
      width: 100%;
      opacity: 0.4;
    }
  }
  p {
    margin: 4px 0 0;
  }
</style>
