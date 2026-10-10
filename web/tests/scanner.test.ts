import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { emit, useBridge } from "../src/lib/bridge";
import { app } from "../src/lib/app.svelte";
import { dialogs } from "../src/lib/dialog.svelte";
import { createFakeBridge } from "../src/lib/fake-bridge";
import { language } from "../src/lib/i18n.svelte";
import type { FileInfo } from "../src/lib/types";
import Scanner from "../src/tools/Scanner.svelte";

let bridge: ReturnType<typeof createFakeBridge>;

const PHOTOS = ["C:\\Fişler\\market.jpg", "C:\\Fişler\\taksi.png", "C:\\Fişler\\otel.jpeg"];

function photo(path: string, kind: FileInfo["kind"] = "image"): FileInfo {
  const name = path.split("\\").pop()!;
  return { path, name, folder: "C:\\Fişler", ext: name.slice(name.lastIndexOf(".")), kind, size: 10, exists: true,
           is_dir: false };
}

const calls = (name: string) => bridge.calls.filter(([call]) => call === name).map(([, args]) => args);
// The pages of the strip (the scan style <select> has options too).
const pages = () => within(screen.getByRole("listbox", { name: "scanner_pages" })).queryAllByRole("option");
const captions = () => pages().map((option) => option.querySelector(".caption")?.textContent);

async function withPages() {
  render(Scanner);
  await fireEvent.click(screen.getByRole("button", { name: "scanner_add_photo" }));
  await waitFor(() => expect(pages()).toHaveLength(3));
}

describe("the scanner page", () => {
  afterEach(() => {
    cleanup();
    dialogs.answer(false);
  });

  beforeEach(() => {
    language.apply({ language: "tr", rtl: false, strings: {
      scanner_page_label: "Sayfa {num}/{total}", scanner_detecting_progress: "Kenarlar {current}/{total}",
    } });
    bridge = createFakeBridge({ jobMs: 30, picks: PHOTOS });
    useBridge(bridge);
    app.page = "scanner";
    app.settingsOpen = false;
    app.viewer = null;
    app.token = "tok";
  });

  it("asks for photos only and shows them in order", async () => {
    await withPages();
    expect(calls("pick_files")).toEqual([["photo", true]]);
    expect(calls("scanner_add")).toEqual([[PHOTOS]]);
    expect(captions()).toEqual(["1", "2", "3"]);
    expect(screen.getByText("Sayfa 1/3")).toBeInTheDocument();
    const thumb = pages()[1].querySelector("img")!;
    expect(thumb.getAttribute("src")).toBe("/scan/tok/p2/thumb?w=360&h=510&v=0");
    expect(screen.getByLabelText("scanner_output_pdf")).toHaveValue("C:\\Fişler\\market_taranmis.pdf");
  });

  it("takes dropped photos and leaves other files alone", async () => {
    render(Scanner);
    await waitFor(() => expect(calls("scanner_open")).toHaveLength(1));
    app.drop([photo("C:\\Belgeler\\rapor.pdf", "pdf"), photo(PHOTOS[0]), photo(PHOTOS[1])]);
    await waitFor(() => expect(pages()).toHaveLength(2));
    expect(calls("scanner_add")).toEqual([[PHOTOS.slice(0, 2)]]);
  });

  it("names a page with a double click and keeps the name on Enter", async () => {
    await withPages();
    await fireEvent.dblClick(pages()[1]);
    const box = screen.getByLabelText("scanner_page_rename");
    await fireEvent.input(box, { target: { value: "Taksi fişi" } });
    await fireEvent.keyDown(box, { key: "Enter" });
    await waitFor(() => expect(captions()[1]).toBe("2 · Taksi fişi"));
    expect(calls("scanner_rename")).toEqual([["p2", "Taksi fişi"]]);
  });

  it("Escape forgets a name being typed, Tab goes on to the next page", async () => {
    await withPages();
    await fireEvent.dblClick(pages()[0]);
    let box = screen.getByLabelText("scanner_page_rename");
    await fireEvent.input(box, { target: { value: "Kapak" } });
    await fireEvent.keyDown(box, { key: "Tab" });
    box = screen.getByLabelText("scanner_page_rename");
    await fireEvent.input(box, { target: { value: "yok" } });
    await fireEvent.keyDown(box, { key: "Escape" });
    await waitFor(() => expect(captions()).toEqual(["1 · Kapak", "2", "3"]));
  });

  it("moves a page with the right-click menu and the keyboard", async () => {
    await withPages();
    await fireEvent.contextMenu(pages()[2]);
    await fireEvent.click(within(screen.getByRole("menu")).getByRole("menuitem", { name: "scanner_page_to_start" }));
    await waitFor(() => expect(calls("scanner_move")).toEqual([["p3", 0]]));
    expect(screen.queryByRole("menu")).toBeNull();

    const strip = screen.getByRole("listbox");
    await fireEvent.keyDown(strip, { key: "ArrowRight" });
    await waitFor(() => expect(screen.getByText("Sayfa 2/3")).toBeInTheDocument());
    await fireEvent.keyDown(strip, { key: "ArrowRight", altKey: true });
    await waitFor(() => expect(calls("scanner_move")).toContainEqual(["p1", 2]));
    await fireEvent.keyDown(strip, { key: "Delete" });
    await waitFor(() => expect(pages()).toHaveLength(2));
    expect(calls("scanner_remove")).toEqual([["p1"]]);
  });

  it("asks before clearing every page", async () => {
    await withPages();
    await fireEvent.click(screen.getByRole("button", { name: "scanner_clear_all" }));
    expect(dialogs.open?.body).toBe("scanner_clear_all_confirm");
    dialogs.answer(false);
    expect(calls("scanner_clear")).toEqual([]);
    await fireEvent.click(screen.getByRole("button", { name: "scanner_clear_all" }));
    dialogs.answer(true);
    await waitFor(() => expect(pages()).toHaveLength(0));
  });

  it("asks before replacing a file it suggested, exports, and starts afresh", async () => {
    await withPages();
    await fireEvent.click(screen.getByRole("button", { name: "scanner_btn" }));
    // The fake says every file exists.
    await waitFor(() => expect(dialogs.open?.title).toBe("overwrite_title"));
    dialogs.answer(true);
    await waitFor(() => expect(calls("scanner_export")).toHaveLength(1));
    await screen.findByRole("button", { name: "feedback_open_output" });
    await waitFor(() => expect(screen.getByLabelText("scanner_output_pdf")).toHaveValue(""));
  });

  it("says what is missing before an export", async () => {
    render(Scanner);
    await fireEvent.click(screen.getByRole("button", { name: "scanner_btn" }));
    expect(screen.getByText("scanner_no_image")).toBeInTheDocument();
    expect(calls("scanner_export")).toEqual([]);
  });

  it("locks the pages while Python works on them and shows what it says", async () => {
    await withPages();
    const state = await bridge.scanner_select(0);
    emit("scanner", { ...state, busy: "detecting", progress: { current: 1, total: 3 } });
    await waitFor(() => expect(screen.getByRole("button", { name: "scanner_add_photo" })).toBeDisabled());
    expect(screen.getByRole("button", { name: "scanner_btn" })).toBeDisabled();
    expect(screen.getAllByText("Kenarlar 1/3").length).toBeGreaterThan(0);
    emit("scanner", { ...state, notice: { tone: "info", title: "Kırpma Alanı", message: "3 sayfa bulundu" } });
    await screen.findByText("3 sayfa bulundu");
    expect(screen.getByRole("button", { name: "scanner_add_photo" })).toBeEnabled();
  });
});
