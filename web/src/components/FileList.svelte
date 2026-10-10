<script lang="ts">
  // An ordered list of files with Add / Remove / Up / Down beside it (the
  // merge and image lists). Arrow keys move the selection; Alt+arrows move
  // the file; Delete removes it.
  import { t } from "../lib/i18n.svelte";
  import type { FileInfo } from "../lib/types";
  import Icon from "./Icon.svelte";

  let { files = $bindable([]), selected = $bindable(-1), label, empty, onadd, onselect }:
    { files: FileInfo[]; selected?: number; label: string; empty: string; onadd: () => void;
      onselect?: (file: FileInfo) => void } = $props();
  let list: HTMLElement | undefined = $state();

  function select(index: number) {
    if (index < 0 || index >= files.length) return;
    selected = index;
    onselect?.(files[index]);
    (list?.children[index] as HTMLElement | undefined)?.scrollIntoView?.({ block: "nearest" });
  }

  function move(step: number) {
    const target = selected + step;
    if (selected < 0 || target < 0 || target >= files.length) return;
    const next = [...files];
    [next[selected], next[target]] = [next[target], next[selected]];
    files = next;
    select(target);
  }

  function remove() {
    if (selected < 0) return;
    files = files.filter((_file, index) => index !== selected);
    const next = Math.min(selected, files.length - 1);
    selected = -1;
    if (next >= 0) select(next);
  }

  function key(event: KeyboardEvent) {
    const step = event.key === "ArrowUp" ? -1 : event.key === "ArrowDown" ? 1 : 0;
    if (step) {
      event.preventDefault();
      if (event.altKey) move(step);
      else select(selected < 0 ? 0 : selected + step);
    } else if (event.key === "Delete") {
      event.preventDefault();
      remove();
    }
  }
</script>

<div class="file-list">
  <div class="box">
    {#if files.length === 0}
      <button class="empty small" type="button" onclick={onadd}>{empty}</button>
    {:else}
      <ul bind:this={list} role="listbox" aria-label={label} tabindex="0" onkeydown={key}
          aria-activedescendant={selected >= 0 ? `file-${selected}` : undefined}>
        {#each files as file, index (file.path + index)}
          <!-- svelte-ignore a11y_click_events_have_key_events -->
          <li id="file-{index}" role="option" aria-selected={index === selected} class:selected={index === selected}
              title={file.path} onclick={() => select(index)}>
            <Icon name={file.kind === "image" ? "SCAN" : "DOCUMENT"} size={13} />
            <span class="ellipsis" dir="auto">{file.name}</span>
          </li>
        {/each}
      </ul>
    {/if}
  </div>
  <div class="controls">
    <button class="btn btn-secondary" type="button" onclick={onadd}><Icon name="ADD" size={12} />{t("str_add")}</button>
    <button class="btn btn-ghost" type="button" disabled={selected < 0} onclick={remove}>
      <Icon name="DELETE" size={12} />{t("str_remove")}
    </button>
    <button class="btn btn-secondary btn-small" type="button" title="Alt+↑" disabled={selected <= 0}
            onclick={() => move(-1)}><Icon name="UP" size={12} />{t("str_up")}</button>
    <button class="btn btn-secondary btn-small" type="button" title="Alt+↓"
            disabled={selected < 0 || selected >= files.length - 1} onclick={() => move(1)}>
      <Icon name="DOWN" size={12} />{t("str_down")}
    </button>
  </div>
</div>

<style>
  .file-list {
    display: flex;
    gap: 14px;
    min-height: 0;
  }
  .box {
    flex: 1 1 auto;
    min-width: 0;
    min-height: 200px;
    display: flex;
    background: var(--field);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    overflow: hidden;
  }
  .box:focus-within {
    border-color: var(--accent);
    box-shadow: 0 0 0 2px var(--focus-ring);
  }
  ul {
    flex: 1;
    list-style: none;
    margin: 0;
    padding: 4px;
    overflow-y: auto;
    max-height: 320px;
  }
  ul:focus-visible {
    outline: none;
  }
  li {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 5px 8px;
    border-radius: var(--radius-sm);
    color: var(--text);
  }
  li :global(.icon) {
    color: var(--text-tertiary);
    flex: none;
  }
  li:hover {
    background: var(--hover);
  }
  li.selected {
    background: var(--accent-subtle-hover);
  }
  .empty {
    flex: 1;
    border: 0;
    background: transparent;
    color: var(--text-tertiary);
    padding: 24px;
    text-align: center;
  }
  .empty:hover {
    color: var(--text-secondary);
  }
  .controls {
    display: flex;
    flex-direction: column;
    gap: 8px;
    flex: none;
  }
</style>
