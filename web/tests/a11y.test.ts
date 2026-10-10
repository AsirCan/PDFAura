// #25 layer 6: every page of the window through axe (names, roles, labels,
// focusable things a keyboard can reach). Colour contrast is not checked
// here -- jsdom draws nothing -- but in Python, on the theme's own tokens
// (tests/test_ui_theme.py, WCAG AA).
import { cleanup, render, waitFor } from "@testing-library/svelte";
import axe from "axe-core";
import { tick } from "svelte";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import App from "../src/App.svelte";
import { app, PAGES } from "../src/lib/app.svelte";
import { useBridge } from "../src/lib/bridge";
import { createFakeBridge } from "../src/lib/fake-bridge";

const RULES = { "color-contrast": { enabled: false } };

async function problems() {
  const result = await axe.run(document.body, { rules: RULES, resultTypes: ["violations"] });
  return result.violations.map((v) => `${v.id}: ${v.help} -> ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`);
}

describe("accessibility", () => {
  beforeAll(() => {
    useBridge(createFakeBridge({ jobMs: 0, picks: ["C:\\Fişler\\market.jpg", "C:\\Fişler\\taksi.png"] }));
  });
  afterEach(() => {
    cleanup();
    app.settingsOpen = false;
    app.viewer = null;
  });

  it.each(PAGES)("the %s page has no axe violations", async (page) => {
    render(App);
    await waitFor(() => expect(app.ready).toBe(true));
    app.page = page;
    await tick();
    expect(await problems()).toEqual([]);
  });

  it("Settings has no axe violations", async () => {
    render(App);
    await waitFor(() => expect(app.ready).toBe(true));
    app.settingsOpen = true;
    await tick();
    expect(await problems()).toEqual([]);
  });

  it("the scanner with pages, and the full viewer, have no axe violations", async () => {
    render(App);
    await waitFor(() => expect(app.ready).toBe(true));
    app.page = "scanner";
    await tick();
    app.drop([
      { path: "C:\\Fişler\\market.jpg", name: "market.jpg", folder: "C:\\Fişler", ext: ".jpg", kind: "image", size: 1,
        exists: true, is_dir: false },
    ]);
    await waitFor(() => expect(document.querySelectorAll(".strip li")).toHaveLength(1));
    expect(await problems()).toEqual([]);
    app.viewer = "C:\\Belgeler\\rapor.pdf";
    await tick();
    expect(await problems()).toEqual([]);
  });
});
