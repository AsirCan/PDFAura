<script lang="ts" module>
  export interface MenuItem {
    label: string;
    action: () => void;
    shortcut?: string;
    disabled?: boolean;
    /** A line above this item. */
    separated?: boolean;
  }
</script>

<script lang="ts">
  // A right-click menu at the pointer: arrow keys move, Enter picks, Esc or a
  // click elsewhere closes it, and it never runs off the window.
  import { onMount } from "svelte";

  let { items, x, y, label, onclose }:
    { items: MenuItem[]; x: number; y: number; label: string; onclose: () => void } = $props();

  let menu: HTMLDivElement | undefined = $state();
  let menuW = $state(0);
  let menuH = $state(0);
  let left = $derived(Math.max(4, Math.min(x, window.innerWidth - menuW - 4)));
  let top = $derived(Math.max(4, Math.min(y, window.innerHeight - menuH - 4)));

  function buttons() {
    return [...(menu?.querySelectorAll<HTMLButtonElement>("button:not(:disabled)") ?? [])];
  }

  onMount(() => {
    const previous = document.activeElement as HTMLElement | null;
    buttons()[0]?.focus();
    const outside = (event: PointerEvent) => {
      if (!menu?.contains(event.target as Node)) onclose();
    };
    window.addEventListener("pointerdown", outside, true);
    window.addEventListener("blur", onclose);
    return () => {
      window.removeEventListener("pointerdown", outside, true);
      window.removeEventListener("blur", onclose);
      if (menu?.contains(document.activeElement)) previous?.focus?.();
    };
  });

  function key(event: KeyboardEvent) {
    const all = buttons();
    const at = all.indexOf(document.activeElement as HTMLButtonElement);
    const moves: Record<string, number> = { ArrowDown: 1, ArrowUp: -1 };
    if (event.key in moves) {
      all[(at + moves[event.key] + all.length) % all.length]?.focus();
    } else if (event.key === "Home") {
      all[0]?.focus();
    } else if (event.key === "End") {
      all[all.length - 1]?.focus();
    } else if (event.key === "Escape" || event.key === "Tab") {
      onclose();
    } else {
      return;
    }
    event.preventDefault();
    event.stopPropagation();
  }

  function pick(item: MenuItem) {
    onclose();
    item.action();
  }
</script>

<div class="menu card" role="menu" aria-label={label} tabindex="-1" bind:this={menu} bind:clientWidth={menuW}
     bind:clientHeight={menuH} style:left="{left}px" style:top="{top}px" onkeydown={key}
     oncontextmenu={(event) => event.preventDefault()}>
  {#each items as item (item.label)}
    {#if item.separated}<hr class="divider" />{/if}
    <button class="item body" role="menuitem" type="button" disabled={item.disabled} onclick={() => pick(item)}>
      <span class="grow">{item.label}</span>
      {#if item.shortcut}<span class="small faint">{item.shortcut}</span>{/if}
    </button>
  {/each}
</div>

<style>
  .menu {
    position: fixed;
    z-index: 30;
    min-width: 200px;
    padding: 4px;
    box-shadow: 0 8px 24px color-mix(in srgb, var(--stage) 25%, transparent);
  }
  .item {
    display: flex;
    align-items: center;
    gap: 24px;
    width: 100%;
    padding: 6px 10px;
    border: 0;
    border-radius: var(--radius-sm);
    background: transparent;
    color: var(--text);
    text-align: start;
  }
  .item:hover:not(:disabled),
  .item:focus-visible {
    background: var(--hover);
    outline: none;
  }
  .item:disabled {
    color: var(--text-disabled);
  }
  .divider {
    margin: 4px 6px;
  }
</style>
