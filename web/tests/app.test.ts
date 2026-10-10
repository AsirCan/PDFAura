import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { beforeEach, describe, expect, it } from "vitest";
import App from "../src/App.svelte";
import { emit, useBridge } from "../src/lib/bridge";
import { app } from "../src/lib/app.svelte";
import { createFakeBridge } from "../src/lib/fake-bridge";

const STRINGS: Record<string, string> = {
  txt_compress: "Sıkıştır", txt_edit: "Düzenle", txt_scan: "Belge Tara", txt_convert: "Dönüştür",
  txt_security: "Güvenlik", txt_advanced: "Gelişmiş", txt_batch: "Toplu İşlemler", txt_settings: "Ayarlar",
  page_meta_compress_title: "PDF sıkıştırma", page_meta_organize_title: "Sayfaları düzenle",
  str_input_pdf: "Girdi PDF",
};

let bridge: ReturnType<typeof createFakeBridge>;

async function start() {
  render(App);
  await waitFor(() => expect(screen.getByRole("navigation")).toBeInTheDocument());
}

describe("the window", () => {
  beforeEach(() => {
    bridge = createFakeBridge({ strings: STRINGS, jobMs: 50 });
    useBridge(bridge);
    app.page = "compress";
    app.settingsOpen = false;
    app.viewer = null;
    app.ready = false;
  });

  it("lists the seven tools in order", async () => {
    await start();
    const items = screen.getAllByRole("button").filter((button) => button.closest(".nav"));
    expect(items.map((item) => item.querySelector("span")?.textContent)).toEqual([
      "Sıkıştır", "Düzenle", "Belge Tara", "Dönüştür", "Güvenlik", "Gelişmiş", "Toplu İşlemler"]);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("PDF sıkıştırma");
  });

  it("switches tools with Ctrl+1…7 and opens Settings with Ctrl+,", async () => {
    await start();
    await fireEvent.keyDown(window, { key: "2", ctrlKey: true });
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Sayfaları düzenle");
    await fireEvent.keyDown(window, { key: ",", ctrlKey: true });
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Ayarlar");
    await fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Sayfaları düzenle");
  });

  it("puts the assistant field under Ctrl+K", async () => {
    await start();
    await fireEvent.keyDown(window, { key: "k", ctrlKey: true });
    expect(document.activeElement?.getAttribute("type")).toBe("text");
    expect(document.activeElement?.closest(".command")).not.toBeNull();
  });

  it("follows the chosen theme and tells Python which one shows", async () => {
    await start();
    expect(document.documentElement.dataset.theme).toBe("paper");
    app.theme = "night";
    await waitFor(() => expect(document.documentElement.dataset.theme).toBe("night"));
    await waitFor(() => expect(bridge.calls).toContainEqual(["theme_shown", ["night"]]));
  });

  it("gives a dropped PDF to the open tool and shows it in the preview", async () => {
    await start();
    emit("drop", { files: [{ path: "C:\\Belgeler\\rapor.pdf", name: "rapor.pdf", folder: "C:\\Belgeler",
                             ext: ".pdf", kind: "pdf", size: 2048, exists: true, is_dir: false }] });
    const input = await screen.findByDisplayValue("C:\\Belgeler\\rapor.pdf");
    expect(input).toHaveAttribute("id", "compress-input");
    await waitFor(() => expect(screen.getByDisplayValue("C:\\Belgeler\\rapor_compress.pdf")).toBeInTheDocument());
    expect(app.preview).toBe("C:\\Belgeler\\rapor.pdf");
    await waitFor(() => expect(bridge.calls).toContainEqual(["document", ["C:\\Belgeler\\rapor.pdf"]]));
  });

  it("shows an assistant reply until it is closed", async () => {
    await start();
    emit("assistant-reply", { text: "rapor.pdf sıkıştırıldı" });
    const reply = await screen.findByRole("status");
    expect(reply).toHaveTextContent("rapor.pdf sıkıştırıldı");
    await fireEvent.click(reply.querySelector("button")!);
    expect(screen.queryByRole("status")).toBeNull();
  });
});
