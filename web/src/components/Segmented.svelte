<script lang="ts" generics="T extends string">
  // One choice out of a few, side by side (SegmentedControl in widgets.py).
  // Arrow keys move between the options, as in a radio group.
  let { options, value = $bindable(), label, onchange, canvas = false }:
    { options: { value: T; label: string }[]; value: T; label: string; onchange?: (value: T) => void;
      canvas?: boolean } = $props();

  let buttons: HTMLButtonElement[] = $state([]);

  function choose(next: T) {
    if (next === value) return;
    value = next;
    onchange?.(next);
  }

  function key(event: KeyboardEvent, index: number) {
    const rtl = document.documentElement.dir === "rtl";
    const forward = event.key === (rtl ? "ArrowLeft" : "ArrowRight") || event.key === "ArrowDown";
    const back = event.key === (rtl ? "ArrowRight" : "ArrowLeft") || event.key === "ArrowUp";
    if (!forward && !back) return;
    event.preventDefault();
    const next = (index + (forward ? 1 : -1) + options.length) % options.length;
    choose(options[next].value);
    buttons[next]?.focus();
  }
</script>

<div class="segmented" class:canvas role="radiogroup" aria-label={label}>
  {#each options as option, index (option.value)}
    <button
      bind:this={buttons[index]}
      type="button"
      role="radio"
      class="segment label"
      class:selected={option.value === value}
      aria-checked={option.value === value}
      tabindex={option.value === value ? 0 : -1}
      onclick={() => choose(option.value)}
      onkeydown={(event) => key(event, index)}
    >
      {option.label}
    </button>
  {/each}
</div>

<style>
  .segmented {
    display: flex;
    flex-wrap: wrap;
    gap: 2px;
    padding: 4px;
    background: var(--sunken);
    border-radius: calc(var(--radius) + 1px);
  }
  .segmented.canvas {
    display: inline-flex;
    background: var(--hover);
  }
  .segment {
    flex: 1 1 auto;
    padding: 5px 12px;
    border: 1px solid transparent;
    border-radius: calc(var(--radius) - 1px);
    background: transparent;
    color: var(--text-secondary);
    white-space: nowrap;
  }
  .segmented:not(.canvas) .segment {
    flex-basis: 22%;
  }
  .segment:hover {
    background: var(--hover);
    color: var(--text);
  }
  .canvas .segment:hover {
    background: var(--pressed);
  }
  .segment.selected {
    background: var(--surface);
    border-color: var(--border-subtle);
    color: var(--text);
  }
</style>
