<script lang="ts">
  // A theme choice with a small picture of a window in that theme. The
  // picture uses the theme's own variables ([data-theme] on the element).
  import type { ThemeName, ThemePreference } from "../lib/types";

  let { value, label, selected, onchoose }:
    { value: ThemePreference; label: string; selected: boolean; onchoose: (value: ThemePreference) => void } =
    $props();
  let halves: ThemeName[] = $derived(value === "system" ? ["paper", "night"] : [value]);
</script>

<button class="theme-card body-strong" class:selected role="radio" aria-checked={selected}
        onclick={() => onchoose(value)}>
  <span class="picture" class:split={halves.length > 1}>
    {#each halves as theme (theme)}
      <span class="window" data-theme={theme}>
        <span class="rail"><i></i><i></i><i></i></span>
        <span class="page">
          <i class="line strong"></i><i class="line"></i><i class="line short"></i><i class="action"></i>
        </span>
      </span>
    {/each}
  </span>
  <span>{label}</span>
</button>

<style>
  .theme-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    padding: 10px 10px 8px;
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-lg);
    background: var(--surface);
    color: var(--text-secondary);
  }
  .theme-card:hover {
    background: var(--surface-subtle);
    border-color: var(--border-strong);
    color: var(--text);
  }
  .theme-card.selected {
    background: var(--accent-subtle);
    border-color: var(--accent);
    color: var(--accent-text);
  }
  .picture {
    display: flex;
    width: 112px;
    height: 68px;
    border-radius: var(--radius);
    overflow: hidden;
    border: 1px solid var(--border-subtle);
  }
  .window {
    flex: 1 1 0;
    display: flex;
    gap: 6px;
    padding: 6px;
    background: var(--canvas);
    overflow: hidden;
  }
  .split .window:first-child {
    padding-inline-end: 0;
  }
  .rail {
    width: 22px;
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding: 4px;
    background: var(--sidebar);
    border-radius: 3px;
  }
  .rail i {
    height: 3px;
    border-radius: 2px;
    background: var(--border);
  }
  .page {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 5px;
    padding: 7px;
    background: var(--surface);
    border-radius: 3px;
    min-width: 50px;
  }
  .line {
    height: 3px;
    border-radius: 2px;
    background: var(--text-secondary);
  }
  .line.strong {
    background: var(--text);
    width: 70%;
  }
  .line.short {
    width: 55%;
  }
  .action {
    margin-top: auto;
    width: 26px;
    height: 7px;
    border-radius: 2px;
    background: var(--accent);
  }
</style>
