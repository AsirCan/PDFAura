// Faz 0 measurements. Each bench* function returns plain numbers so the
// --bench run can write them to JSON for the report.
"use strict";

const $ = (s) => document.querySelector(s);
const api = () => window.pywebview.api;
const now = () => performance.now();
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const round = (x, d = 1) => Math.round(x * 10 ** d) / 10 ** d;

function stats(values) {
  const v = [...values].sort((a, b) => a - b);
  const at = (q) => v[Math.min(v.length - 1, Math.floor(q * v.length))];
  return { n: v.length, median: round(at(0.5)), p95: round(at(0.95)), max: round(v[v.length - 1]) };
}

function show(el, value) {
  $(el).textContent = typeof value === "string" ? value : JSON.stringify(value, null, 1);
}

// Counts frames while `work` runs: a frozen UI shows up as long frames.
async function framesDuring(work) {
  let frames = 0, longest = 0, long = 0, last = now(), running = true;
  const tick = () => {
    const t = now(), gap = t - last;
    last = t; frames++;
    longest = Math.max(longest, gap);
    if (gap > 50) long++;
    if (running) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
  const t0 = now();
  const result = await work();
  running = false;
  const seconds = (now() - t0) / 1000;
  return { result, fps: round(frames / seconds), longest_frame_ms: round(longest), frames_over_50ms: long };
}

// ── Bridge ─────────────────────────────────────────────────────────────
async function benchPing(n = 200) {
  const times = [];
  for (let i = 0; i < n; i++) {
    const t0 = now();
    await api().ping({ i, s: "x".repeat(64) });
    times.push(now() - t0);
  }
  return stats(times);
}

// ── Image transport ────────────────────────────────────────────────────
async function loadImage(img, src) {
  img.src = src;
  await img.decode();
}

async function benchPhoto() {
  const out = {};
  const img = $("#photo");
  for (const side of [1600, 2560, 4000]) {
    for (const mode of ["data", "http"]) {
      const times = [];
      let info;
      for (let r = 0; r < 3; r++) {
        const t0 = now();
        info = await api().photo(mode, side);
        await loadImage(img, info.src);
        times.push(now() - t0);
      }
      out[`${mode}_${side}`] = { ...stats(times), jpeg_kb: Math.round(info.bytes / 1024), py_ms: info.py_ms };
    }
  }
  return out;
}

// ── Thumbnails ─────────────────────────────────────────────────────────
function makeGrid(count) {
  const grid = $("#thumbs");
  grid.replaceChildren();
  grid.scrollTop = 0;
  const imgs = [];
  for (let i = 0; i < count; i++) {
    const img = document.createElement("img");
    img.alt = "";
    img.dataset.index = String(i);
    grid.append(img);
    imgs.push(img);
  }
  return { grid, imgs };
}

async function scrollThrough(grid, ms = 4000) {
  const start = now(), max = grid.scrollHeight - grid.clientHeight;
  while (now() - start < ms) {
    grid.scrollTop = ((now() - start) / ms) * max;
    await new Promise(requestAnimationFrame);
  }
  grid.scrollTop = max;
}

// data: every thumbnail is a js_api call; an IntersectionObserver asks for
// the visible ones, at most 4 at a time.
async function benchThumbsData(count) {
  const { grid, imgs } = makeGrid(count);
  const queue = [], requested = new Set();
  let active = 0, loaded = 0, firstScreen = null;
  const t0 = now();
  const pump = () => {
    while (active < 4 && queue.length) {
      const img = queue.shift();
      active++;
      api().thumb(Number(img.dataset.index), 220).then(async (src) => {
        await loadImage(img, src);
        active--; loaded++;
        if (loaded === 12 && firstScreen === null) firstScreen = now() - t0;
        pump();
      });
    }
  };
  const io = new IntersectionObserver((entries) => {
    for (const e of entries) {
      if (e.isIntersecting && !requested.has(e.target)) {
        requested.add(e.target); queue.push(e.target);
      }
    }
    pump();
  }, { root: grid, rootMargin: "200px" });
  imgs.forEach((img) => io.observe(img));
  while (firstScreen === null) await sleep(10);
  const scroll = await framesDuring(() => scrollThrough(grid));
  io.disconnect();
  return { first_screen_ms: round(firstScreen), scroll_fps: scroll.fps, longest_frame_ms: scroll.longest_frame_ms,
           frames_over_50ms: scroll.frames_over_50ms, loaded_after_scroll: loaded };
}

// http: plain <img loading="lazy" src="/thumb/...">; the browser schedules
// the requests itself and no js_api call is involved.
async function benchThumbsHttp(count) {
  const base = await api().thumb_base();
  const { grid, imgs } = makeGrid(count);
  let loaded = 0, firstScreen = null;
  const t0 = now();
  imgs.forEach((img, i) => {
    img.loading = "lazy";
    img.addEventListener("load", () => {
      loaded++;
      if (loaded === 12 && firstScreen === null) firstScreen = now() - t0;
    }, { once: true });
    img.src = `${base}${i}?w=220`;
  });
  while (firstScreen === null) await sleep(10);
  const scroll = await framesDuring(() => scrollThrough(grid));
  return { first_screen_ms: round(firstScreen), scroll_fps: scroll.fps, longest_frame_ms: scroll.longest_frame_ms,
           frames_over_50ms: scroll.frames_over_50ms, loaded_after_scroll: loaded };
}

// ── Python -> JS events ────────────────────────────────────────────────
let received = 0;
window.spike = {
  progress(i, n) { received = i; $("#bar").value = i / n; },
  dropped(paths) { show("#drop-out", paths.join("\n")); },
};

async function benchBurst(n, blocking) {
  received = 0;
  const run = await framesDuring(async () => {
    const t0 = now();
    const pyMs = await (blocking ? api().burst_blocking(n) : api().burst(n));
    while (received < n && now() - t0 < 20000) await sleep(5);
    return { py_ms: pyMs, all_arrived_ms: round(now() - t0), received };
  });
  return { ...run.result, fps: run.fps, longest_frame_ms: run.longest_frame_ms };
}

// ── CSP, theme, fonts ──────────────────────────────────────────────────
function pageEval() {
  try {
    // eslint-disable-next-line no-eval
    return eval("1 + 1") === 2 ? "allowed" : "?";
  } catch (e) {
    return `blocked (${e.name})`;
  }
}

async function renderSamples() {
  const box = $("#samples");
  box.replaceChildren();
  const widths = {};
  for (const s of await api().samples()) {
    const line = document.createElement("div");
    line.lang = s.code;
    if (s.rtl) line.dir = "rtl";
    line.textContent = `${s.name}: ${s.text}:`;
    box.append(line);
    widths[s.code] = Math.round(line.getBoundingClientRect().height);
  }
  return widths;
}

function themeInfo() {
  return { prefers_dark: matchMedia("(prefers-color-scheme: dark)").matches };
}

// ── Wiring ─────────────────────────────────────────────────────────────
async function runAll() {
  $("#status").textContent = "ölçülüyor…";
  const results = { page_eval: pageEval(), theme: themeInfo() };
  results.ping = await benchPing(); show("#ping-out", results.ping);
  results.photo = await benchPhoto(); show("#photo-out", results.photo);
  const count = await api().page_count();
  results.thumbs_data = await benchThumbsData(count);
  results.thumbs_http = await benchThumbsHttp(count);
  show("#thumbs-out", { data: results.thumbs_data, http: results.thumbs_http });
  results.burst_run_js = await benchBurst(1000, false);
  results.burst_evaluate_js = await benchBurst(200, true);
  show("#burst-out", { run_js: results.burst_run_js, evaluate_js: results.burst_evaluate_js });
  results.sample_line_heights = await renderSamples();
  $("#status").textContent = "bitti";
  return results;
}

window.addEventListener("pywebviewready", async () => {
  const ready = await api().ready();
  $("#status").textContent = `hazır (${ready.since_start_ms} ms)`;
  const info = await api().info();
  show("#info", { ...info, page_eval: pageEval() });
  show("#theme-out", themeInfo());
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => show("#theme-out", themeInfo()));
  await renderSamples();

  $("#run-all").onclick = async () => api().report(await runAll());
  $("#ping-btn").onclick = async () => show("#ping-out", await benchPing());
  $("#open-btn").onclick = async () => show("#dialog-out", await api().pick_files());
  $("#folder-btn").onclick = async () => show("#dialog-out", await api().pick_folder());
  $("#save-btn").onclick = async () => show("#dialog-out", String(await api().pick_save()));
  $("#photo-btn").onclick = async () => show("#photo-out", await benchPhoto());
  $("#thumbs-data-btn").onclick = async () => show("#thumbs-out", await benchThumbsData(await api().page_count()));
  $("#thumbs-http-btn").onclick = async () => show("#thumbs-out", await benchThumbsHttp(await api().page_count()));
  $("#burst-btn").onclick = async () => show("#burst-out", await benchBurst(1000, false));

  const zone = $("#drop-zone");
  zone.addEventListener("dragenter", () => zone.classList.add("over"));
  zone.addEventListener("dragleave", () => zone.classList.remove("over"));
  zone.addEventListener("drop", () => zone.classList.remove("over"));
  window.__wired = true;

  if ((await api().config()).bench) await api().report(await runAll());
});
