<script lang="ts">
  // The photo with the four corner handles. A handle follows the pointer
  // without asking Python;
  // the corners go to Python once, when it is let go. While a handle moves,
  // a loupe shows the photo around it at twice the size, drawn here from
  // the same picture.
  import { untrack } from "svelte";
  import { t } from "../../lib/i18n.svelte";
  import { photoUrl } from "../../lib/scanner.svelte";
  import type { Point, ScanPage } from "../../lib/types";

  let { page, large = false, locked = false, oncommit }:
    { page: ScanPage; large?: boolean; locked?: boolean; oncommit: (corners: Point[]) => void } = $props();

  const LOUPE = 200;
  const ZOOM = 2;
  // Room around the photo, so a handle on its edge is whole and can be held.
  let pad = $derived(large ? 24 : 14);
  let radius = $derived(large ? 12 : 8);

  let stage: HTMLDivElement | undefined = $state();
  let stageW = $state(0);
  let stageH = $state(0);
  let corners = $state<Point[]>([]);
  /** The handle being dragged or moved with the keyboard. */
  let active = $state<number | null>(null);
  let pointer = $state<{ x: number; y: number } | null>(null);
  let loaded = $state(false);
  let keyTimer: ReturnType<typeof setTimeout> | undefined;

  // Python's corners, except while the user is moving one.
  $effect.pre(() => {
    const next = page.corners;
    if (untrack(() => active) === null) corners = next.map(([x, y]) => [x, y] as Point);
  });

  let src = $derived(photoUrl(page));
  $effect(() => {
    void src;
    loaded = false;
  });

  let fit = $derived.by(() => {
    if (stageW < 40 || stageH < 40 || !page.width || !page.height) return null;
    const scale = Math.min((stageW - pad * 2) / page.width, (stageH - pad * 2) / page.height);
    if (scale <= 0) return null;
    const w = page.width * scale;
    const h = page.height * scale;
    return { scale, w, h, x: (stageW - w) / 2, y: (stageH - h) / 2 };
  });

  let points = $derived(fit ? corners.map(([x, y]) => [fit.x + x * fit.scale, fit.y + y * fit.scale] as Point) : []);

  // Beside the pointer, never over it: above and before it if there is
  // room, else in the first corner around it that fits the stage.
  let loupe = $derived.by(() => {
    if (active === null || !fit || !points[active]) return null;
    const [cx, cy] = points[active];
    const ex = pointer?.x ?? cx;
    const ey = pointer?.y ?? cy;
    const before = ex - LOUPE - 40;
    const after = ex + 40;
    const above = ey - LOUPE - 40;
    const below = ey + 40;
    const fits = ([x, y]: Point) => x >= 0 && y >= 0 && x + LOUPE <= stageW && y + LOUPE <= stageH;
    const spots: Point[] = [[before, above], [after, above], [before, below], [after, below]];
    // A narrow stage: straight above or below the pointer, kept inside.
    const [sx, sy] = spots.find(fits) ?? [ex - LOUPE / 2, above >= 0 ? above : below];
    const x = Math.max(0, Math.min(stageW - LOUPE, sx));
    const y = Math.max(0, Math.min(stageH - LOUPE, sy));
    const bx = LOUPE / 2 - (cx - fit.x) * ZOOM;
    const by = LOUPE / 2 - (cy - fit.y) * ZOOM;
    return { x, y, size: `${fit.w * ZOOM}px ${fit.h * ZOOM}px`, position: `${bx}px ${by}px` };
  });

  function toPhoto(clientX: number, clientY: number): Point | null {
    if (!fit || !stage) return null;
    const rect = stage.getBoundingClientRect();
    const x = (clientX - rect.left - fit.x) / fit.scale;
    const y = (clientY - rect.top - fit.y) / fit.scale;
    return [Math.round(Math.max(0, Math.min(page.width, x))), Math.round(Math.max(0, Math.min(page.height, y)))];
  }

  function grab(event: PointerEvent, index: number) {
    if (locked || event.button !== 0) return;
    event.preventDefault();
    (event.currentTarget as Element).setPointerCapture?.(event.pointerId);
    active = index;
    follow(event);
  }

  function follow(event: PointerEvent) {
    if (active === null || !stage) return;
    const at = toPhoto(event.clientX, event.clientY);
    if (!at) return;
    const rect = stage.getBoundingClientRect();
    pointer = { x: event.clientX - rect.left, y: event.clientY - rect.top };
    corners[active] = at;
  }

  function release() {
    if (active === null) return;
    active = null;
    pointer = null;
    oncommit(corners.map(([x, y]) => [x, y] as Point));
  }

  // Arrow keys move a focused handle a screen pixel (Shift: ten).
  function nudge(event: KeyboardEvent, index: number) {
    const steps: Record<string, Point> = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] };
    const step = steps[event.key];
    if (!step || locked || !fit) return;
    event.preventDefault();
    event.stopPropagation();
    const by = (event.shiftKey ? 10 : 1) / fit.scale;
    const [x, y] = corners[index];
    active = index;
    pointer = null;
    corners[index] = [Math.round(Math.max(0, Math.min(page.width, x + step[0] * by))),
                      Math.round(Math.max(0, Math.min(page.height, y + step[1] * by)))];
    clearTimeout(keyTimer);
    keyTimer = setTimeout(release, 600);
  }

  function blurred() {
    if (pointer === null && active !== null) {
      clearTimeout(keyTimer);
      release();
    }
  }
</script>

<div class="editor" class:large class:locked bind:this={stage} bind:clientWidth={stageW} bind:clientHeight={stageH}>
  {#if fit}
    <img class="photo" class:loaded {src} alt={page.label || page.name} draggable="false"
         style:left="{fit.x}px" style:top="{fit.y}px" style:width="{fit.w}px" style:height="{fit.h}px"
         onload={() => (loaded = true)} />
    <svg class="overlay" width={stageW} height={stageH} aria-hidden={locked}>
      <polygon class="quad" points={points.map((p) => p.join(",")).join(" ")} />
      {#each points as [x, y], index (index)}
        <circle class="hit" cx={x} cy={y} r={radius * 2} role="button" tabindex={locked ? -1 : 0}
                aria-label="{t('scanner_corners_hint')} {index + 1}"
                onpointerdown={(event) => grab(event, index)} onpointermove={follow} onpointerup={release}
                onpointercancel={release} onkeydown={(event) => nudge(event, index)}
                onblur={blurred} />
        <circle class="handle" class:active={active === index} cx={x} cy={y} r={radius} />
      {/each}
    </svg>
    {#if loupe}
      <div class="loupe" style:left="{loupe.x}px" style:top="{loupe.y}px" style:background-image={`url("${src}")`}
           style:background-size={loupe.size} style:background-position={loupe.position}>
        <span class="cross-h"></span>
        <span class="cross-v"></span>
        <span class="dot"></span>
      </div>
    {/if}
  {/if}
</div>

<style>
  .editor {
    position: relative;
    flex: 1 1 auto;
    min-width: 0;
    min-height: 0;
    overflow: hidden;
    background: var(--stage);
    border-radius: var(--radius);
    touch-action: none;
    cursor: crosshair;
  }
  .large {
    border-radius: 0;
  }
  .photo {
    position: absolute;
    display: block;
    opacity: 0;
    transition: opacity 120ms ease-out;
    pointer-events: none;
  }
  .photo.loaded {
    opacity: 1;
  }
  .overlay {
    position: absolute;
    inset: 0;
    overflow: visible;
  }
  .quad {
    fill: none;
    stroke: var(--handle-line);
    stroke-width: 2;
    stroke-dasharray: 6 4;
    pointer-events: none;
  }
  .large .quad {
    stroke-width: 3;
  }
  .hit {
    fill: transparent;
    cursor: grab;
  }
  .hit:focus {
    outline: none;
  }
  .hit:focus-visible + .handle {
    stroke: var(--focus-ring);
    stroke-width: 4;
  }
  .handle {
    fill: var(--handle);
    stroke: var(--handle-ring);
    stroke-width: 2;
    pointer-events: none;
  }
  .handle.active {
    fill: var(--handle-active);
  }
  .locked .hit {
    cursor: default;
  }
  .locked .overlay {
    opacity: 0.55;
  }
  .loupe {
    position: absolute;
    width: 200px;
    height: 200px;
    background-color: var(--stage);
    background-repeat: no-repeat;
    border: 3px solid var(--handle-ring);
    box-sizing: content-box;
    margin: -3px 0 0 -3px;
    image-rendering: pixelated;
    pointer-events: none;
  }
  .cross-h,
  .cross-v,
  .dot {
    position: absolute;
    background: var(--magnifier-cross);
  }
  .cross-h {
    left: 85px;
    top: 99px;
    width: 30px;
    height: 2px;
  }
  .cross-v {
    left: 99px;
    top: 85px;
    width: 2px;
    height: 30px;
  }
  .dot {
    left: 96px;
    top: 96px;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--handle);
    border: 1px solid var(--handle-ring);
    box-sizing: border-box;
  }
</style>
