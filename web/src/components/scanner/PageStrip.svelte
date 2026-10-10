<script lang="ts">
  // The scanner's pages as thumbnails, in PDF order: drag one to reorder,
  // double-click or F2 to name it,
  // right-click for more. Arrow keys select, Alt+arrows move the page,
  // Delete removes it.
  import { t } from "../../lib/i18n.svelte";
  import { thumbUrl, type ScanBoard } from "../../lib/scanner.svelte";
  import type { ScanPage } from "../../lib/types";
  import ContextMenu, { type MenuItem } from "../ContextMenu.svelte";
  import Icon from "../Icon.svelte";

  let { board }: { board: ScanBoard } = $props();

  const DRAG_START_PX = 6;
  const AUTOSCROLL_ZONE = 28;
  const GHOST_W = 56;

  let list: HTMLUListElement | undefined = $state();
  let scroller: HTMLDivElement | undefined = $state();
  let renaming = $state<string | null>(null);
  let draft = $state("");
  let menu = $state<{ x: number; y: number; page: ScanPage } | null>(null);

  // ── Drag to reorder ────────────────────────────────────────────────
  let press: { uid: string; x: number; y: number } | null = null;
  let dragging = $state<string | null>(null);
  let pointer = $state<{ x: number; y: number } | null>(null);
  let slot = $state<{ insert: number; x: number; y: number; w: number; h: number } | null>(null);
  let scrolling = 0;

  let caption = $derived.by(() => {
    if (!board.page) return t("scanner_no_pages");
    const text = t("scanner_page_label", { num: board.current + 1, total: board.pages.length });
    return board.page.label ? `${text} · ${board.page.label}` : text;
  });
  let ghost = $derived(dragging ? board.pages.find((page) => page.uid === dragging) ?? null : null);

  function rtl() {
    return document.documentElement.dir === "rtl";
  }

  function cells() {
    return [...(list?.children ?? [])] as HTMLElement[];
  }

  /** How many thumbnails sit in a row. */
  function columns() {
    const all = cells();
    if (!all.length) return 1;
    const top = all[0].offsetTop;
    return Math.max(1, all.filter((cell) => cell.offsetTop === top).length);
  }

  /** Where a page let go of at (x, y) lands, and the line that shows it. */
  function slotAt(x: number, y: number) {
    const all = cells();
    if (!all.length || !scroller) return null;
    const rects = all.map((cell) => cell.getBoundingClientRect());
    const area = scroller.getBoundingClientRect();
    const dx = -area.left;
    const dy = scroller.scrollTop - area.top;
    const rows: number[][] = [];
    rects.forEach((rect, index) => {
      const row = rows.find((r) => Math.abs(rects[r[0]].top - rect.top) < 2);
      if (row) row.push(index);
      else rows.push([index]);
    });
    if (rows.every((row) => row.length === 1)) {
      let insert = rects.findIndex((rect) => y < rect.top + rect.height / 2);
      if (insert < 0) insert = rects.length;
      const edge = insert < rects.length ? rects[insert].top - 6 : rects[rects.length - 1].bottom + 2;
      const rect = rects[Math.min(insert, rects.length - 1)];
      return { insert, x: rect.left + dx - 4, y: edge + dy, w: rect.width + 8, h: 4 };
    }
    const row = rows.find((r) => y < rects[r[0]].bottom + 6) ?? rows[rows.length - 1];
    const before = row.find((index) => {
      const middle = rects[index].left + rects[index].width / 2;
      return rtl() ? x > middle : x < middle;
    });
    const insert = before ?? row[row.length - 1] + 1;
    const rect = rects[before ?? row[row.length - 1]];
    const startSide = before !== undefined;
    const edge = startSide === rtl() ? rect.right + 2 : rect.left - 6;
    return { insert, x: edge + dx, y: rect.top + dy - 4, w: 4, h: rect.height + 8 };
  }

  function pressed(event: PointerEvent, index: number) {
    if (event.button !== 0 || (event.target as Element).closest("input")) return;
    finishRename();
    list?.focus();
    void board.select(index);
    if (board.locked) return;
    press = { uid: board.pages[index].uid, x: event.clientX, y: event.clientY };
    window.addEventListener("pointermove", moved);
    window.addEventListener("pointerup", released);
    window.addEventListener("pointercancel", endDrag);
  }

  function moved(event: PointerEvent) {
    if (!press) return;
    if (!dragging) {
      if (Math.abs(event.clientX - press.x) < DRAG_START_PX && Math.abs(event.clientY - press.y) < DRAG_START_PX) return;
      if (board.locked) return endDrag();
      dragging = press.uid;
    }
    pointer = { x: event.clientX, y: event.clientY };
    slot = slotAt(event.clientX, event.clientY);
    if (!scrolling) scrolling = requestAnimationFrame(autoscroll);
  }

  function autoscroll() {
    scrolling = 0;
    if (!dragging || !pointer || !scroller) return;
    const area = scroller.getBoundingClientRect();
    const step = pointer.y < area.top + AUTOSCROLL_ZONE ? -8 : pointer.y > area.bottom - AUTOSCROLL_ZONE ? 8 : 0;
    if (!step) return;
    scroller.scrollTop += step;
    slot = slotAt(pointer.x, pointer.y);
    scrolling = requestAnimationFrame(autoscroll);
  }

  function released(event: PointerEvent) {
    const uid = dragging;
    endDrag();
    if (!uid || !scroller) return;
    const area = scroller.getBoundingClientRect();
    if (event.clientX < area.left - 40 || event.clientX > area.right + 40) return;    // let go outside: cancel
    const target = slotAt(event.clientX, Math.max(area.top, Math.min(area.bottom, event.clientY)));
    const from = board.pages.findIndex((page) => page.uid === uid);
    if (!target || from < 0) return;
    const to = target.insert > from ? target.insert - 1 : target.insert;
    if (to !== from) void board.move(board.pages[from], to);
  }

  function endDrag() {
    press = null;
    dragging = null;
    pointer = null;
    slot = null;
    cancelAnimationFrame(scrolling);
    scrolling = 0;
    window.removeEventListener("pointermove", moved);
    window.removeEventListener("pointerup", released);
    window.removeEventListener("pointercancel", endDrag);
  }

  // ── Names ──────────────────────────────────────────────────────────
  function startRename(page: ScanPage) {
    finishRename();
    renaming = page.uid;
    draft = page.label;
  }

  function finishRename(commit = true) {
    const uid = renaming;
    if (!uid) return;
    renaming = null;
    const page = board.pages.find((item) => item.uid === uid);
    if (commit && page && draft.trim() !== page.label) void board.rename(page, draft);
  }

  function renameKey(event: KeyboardEvent, index: number) {
    event.stopPropagation();
    if (event.key === "Enter") {
      event.preventDefault();
      finishRename();
      list?.focus();
    } else if (event.key === "Escape") {
      event.preventDefault();
      finishRename(false);
      list?.focus();
    } else if (event.key === "Tab") {
      // Save this name and go straight on to the next page's.
      event.preventDefault();
      finishRename();
      const next = index + (event.shiftKey ? -1 : 1);
      if (next >= 0 && next < board.pages.length) {
        void board.select(next);
        startRename(board.pages[next]);
      } else {
        list?.focus();
      }
    }
  }

  function focusAndSelect(node: HTMLInputElement) {
    node.focus();
    node.select();
  }

  // ── Menu and keys ──────────────────────────────────────────────────
  function openMenu(event: MouseEvent, index: number) {
    event.preventDefault();
    finishRename();
    if (board.locked) return;
    void board.select(index);
    menu = { x: event.clientX, y: event.clientY, page: board.pages[index] };
  }

  let menuItems = $derived.by((): MenuItem[] => {
    if (!menu) return [];
    const page = menu.page;
    return [
      { label: t("scanner_page_rename"), shortcut: "F2", action: () => startRename(page) },
      { label: t("scanner_page_to_start"), action: () => void board.move(page, 0) },
      { label: t("scanner_page_to_end"), action: () => void board.move(page, board.pages.length - 1) },
      { label: t("scanner_remove_photo"), shortcut: "Del", separated: true, disabled: board.locked,
        action: () => void board.remove(page) },
    ];
  });

  function moveCurrent(step: number) {
    const page = board.page;
    const to = board.current + step;
    if (page && to >= 0 && to < board.pages.length) void board.move(page, to);
  }

  function key(event: KeyboardEvent) {
    if (event.target !== list) return;
    const page = board.page;
    const forward = rtl() ? -1 : 1;
    const steps: Record<string, number> = {
      ArrowLeft: -forward, ArrowRight: forward, ArrowUp: -columns(), ArrowDown: columns(),
    };
    if (event.key in steps) {
      if (event.altKey) moveCurrent(Math.sign(steps[event.key]));
      else void board.select(Math.max(0, Math.min(board.pages.length - 1, board.current + steps[event.key])));
    } else if (event.key === "Home") {
      void board.select(0);
    } else if (event.key === "End") {
      void board.select(board.pages.length - 1);
    } else if (event.key === "F2" && page) {
      startRename(page);
    } else if (event.key === "Delete" && page && !board.locked) {
      void board.remove(page);
    } else if ((event.key === "ContextMenu" || (event.shiftKey && event.key === "F10")) && page) {
      const cell = cells()[board.current]?.getBoundingClientRect();
      if (cell && !board.locked) menu = { x: cell.left + cell.width / 2, y: cell.top + cell.height / 2, page };
    } else if (event.key === "Escape" && dragging) {
      endDrag();
    } else {
      return;
    }
    event.preventDefault();
    event.stopPropagation();
  }

  // The selected page stays in view.
  $effect(() => {
    const index = board.current;
    if (!dragging) cells()[index]?.scrollIntoView?.({ block: "nearest" });
  });
</script>

<div class="strip">
  <h3 class="section-title">{t("scanner_pages")}</h3>
  <p class="caption-line small muted ellipsis" title={caption}>{caption}</p>
  <!-- Narrow strip: one hint per line; wide: both on one. -->
  <p class="hint"><span>{t("scanner_strip_hint_drag")} ·</span>
    <span>{t("scanner_strip_hint_name")}</span></p>
  <div class="scroller" bind:this={scroller}>
    <ul bind:this={list} role="listbox" tabindex="0" aria-label={t("scanner_pages")} onkeydown={key}
        aria-activedescendant={board.page ? `scan-page-${board.page.uid}` : undefined}>
      {#each board.pages as page, index (page.uid)}
        <li id="scan-page-{page.uid}" role="option" aria-selected={index === board.current}
            class:selected={index === board.current} class:moving={dragging === page.uid} title={page.name}
            onpointerdown={(event) => pressed(event, index)} ondblclick={() => startRename(page)}
            oncontextmenu={(event) => openMenu(event, index)}>
          <div class="thumb">
            <img src={thumbUrl(page)} alt="" draggable="false" />
          </div>
          {#if renaming === page.uid}
            <input class="rename" type="text" dir="auto" maxlength="60" spellcheck="false" bind:value={draft}
                   aria-label={t("scanner_page_rename")} use:focusAndSelect
                   onkeydown={(event) => renameKey(event, index)}
                   onblur={() => renaming === page.uid && finishRename()} />
          {:else}
            <span class="caption small ellipsis" dir="auto">{index + 1}{page.label ? ` · ${page.label}` : ""}</span>
          {/if}
        </li>
      {/each}
    </ul>
    {#if slot}
      <span class="drop-line" style:left="{slot.x}px" style:top="{slot.y}px" style:width="{slot.w}px"
            style:height="{slot.h}px"></span>
    {/if}
  </div>
  <div class="buttons">
    <button class="btn btn-secondary btn-small" type="button" title="Alt+↑"
            disabled={board.locked || board.current <= 0} onclick={() => moveCurrent(-1)}>
      <Icon name="UP" size={12} />{t("scanner_move_up")}
    </button>
    <button class="btn btn-secondary btn-small" type="button" title="Alt+↓"
            disabled={board.locked || board.current < 0 || board.current >= board.pages.length - 1}
            onclick={() => moveCurrent(1)}>
      <Icon name="DOWN" size={12} />{t("scanner_move_down")}
    </button>
  </div>
</div>

{#if ghost && pointer}
  <img class="ghost" src={thumbUrl(ghost)} alt="" draggable="false"
       style:left="{pointer.x + 14 + GHOST_W > window.innerWidth ? pointer.x - 14 - GHOST_W : pointer.x + 14}px"
       style:top="{pointer.y + 10}px" />
{/if}

{#if menu}
  <ContextMenu items={menuItems} x={menu.x} y={menu.y} label={t("scanner_pages")} onclose={() => (menu = null)} />
{/if}

<style>
  .strip {
    display: flex;
    flex-direction: column;
    min-width: 0;
    height: 100%;
  }
  h3 {
    margin: 0;
  }
  h3,
  p {
    flex: none;
  }
  p {
    margin: 2px 0 0;
  }
  /* A short window: the thumbnails need the room more than the hint. */
  @media (max-height: 760px) {
    .hint {
      display: none;
    }
    .caption-line {
      margin-bottom: 6px;
    }
  }
  .hint {
    margin-bottom: 8px;
  }
  .hint > span {
    display: inline-block;
    white-space: nowrap;
  }
  .scroller {
    position: relative;
    flex: 1 1 auto;
    min-height: 0;
    overflow-y: auto;
    background: var(--sunken);
    border-radius: var(--radius);
  }
  ul {
    display: grid;
    /* auto-fit: a few pages get fewer, bigger thumbnails. */
    grid-template-columns: repeat(auto-fit, minmax(96px, 1fr));
    gap: 12px;
    margin: 0;
    padding: 10px 8px;
    list-style: none;
    min-height: 100%;
    align-content: start;
  }
  ul:focus-visible {
    outline: 2px solid var(--focus-ring);
    outline-offset: -2px;
    border-radius: var(--radius);
  }
  li {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    min-width: 0;
    max-width: 180px;
    width: 100%;
    justify-self: center;
  }
  .thumb {
    width: 100%;
    aspect-ratio: 2480 / 3508;
    display: grid;
    place-items: center;
    border-radius: var(--radius-sm);
    outline: 2px solid transparent;
    outline-offset: 3px;
  }
  .selected .thumb {
    outline-color: var(--accent);
  }
  .thumb img {
    max-width: 100%;
    max-height: 100%;
    display: block;
    background: var(--surface);
    box-shadow: 0 1px 3px color-mix(in srgb, var(--stage) 25%, transparent);
    pointer-events: none;
  }
  .moving .thumb {
    opacity: 0.4;
    outline: 1px dashed var(--text-tertiary);
  }
  .caption {
    max-width: 100%;
    color: var(--text-secondary);
  }
  .selected .caption {
    color: var(--accent-text);
    font-weight: var(--weight-small-strong);
  }
  .rename {
    width: 100%;
    min-width: 96px;
    padding: 2px 6px;
    border: 2px solid var(--accent);
    border-radius: var(--radius-sm);
    background: var(--field);
    color: var(--text);
    text-align: center;
    font: var(--weight-small) var(--size-small) / 1.3 var(--font-small);
  }
  .drop-line {
    position: absolute;
    border-radius: 2px;
    background: var(--accent);
    pointer-events: none;
  }
  .buttons {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 8px;
  }
  .buttons .btn {
    flex: 1 1 110px;
  }
  .ghost {
    position: fixed;
    z-index: 25;
    width: 56px;
    outline: 2px solid var(--accent);
    background: var(--surface);
    pointer-events: none;
  }
</style>
