<script lang="ts">
  // The frame every tool page is built in: a one-line hint above a card
  // that scrolls when the window is too short for it.
  import type { Snippet } from "svelte";
  import Icon from "./Icon.svelte";

  let { hint, children }: { hint: string; children: Snippet } = $props();
</script>

<div class="tool">
  <p class="hint-strip small">
    <Icon name="INFO" size={13} />
    <span>{hint}</span>
  </p>
  <div class="scroll">
    <div class="card form">
      {@render children()}
    </div>
  </div>
</div>

<style>
  .tool {
    display: flex;
    flex-direction: column;
    min-height: 0;
    height: 100%;
  }
  .hint-strip {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    margin: 0 0 12px;
    padding: 7px 12px;
    background: var(--sunken);
    border-radius: var(--radius);
    color: var(--text-secondary);
  }
  .hint-strip :global(.icon) {
    color: var(--text-tertiary);
    margin-top: 2px;
    flex: none;
  }
  .scroll {
    flex: 1 1 auto;
    min-height: 0;
    overflow-y: auto;
    scrollbar-gutter: stable;
  }
  .form {
    min-height: 100%;
    padding: 24px;
  }
</style>
