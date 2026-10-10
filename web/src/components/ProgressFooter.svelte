<script lang="ts">
  // A tool's action row: the main button, then progress and Cancel while a
  // job runs (ProgressFooter in helpers.py).
  import { t } from "../lib/i18n.svelte";
  import type { ToolRun } from "../lib/run.svelte";

  let { run, label, onaction, disabled = false }:
    { run: ToolRun; label: string; onaction: () => void; disabled?: boolean } = $props();
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
    {#if run.busy || run.finished}
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
  p {
    margin: 4px 0 0;
  }
</style>
