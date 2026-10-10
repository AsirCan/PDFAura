import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { beforeEach, describe, expect, it } from "vitest";
import { useBridge } from "../src/lib/bridge";
import { app } from "../src/lib/app.svelte";
import { createFakeBridge } from "../src/lib/fake-bridge";
import { language } from "../src/lib/i18n.svelte";
import type { FileInfo } from "../src/lib/types";
import Advanced from "../src/tools/Advanced.svelte";
import Batch from "../src/tools/Batch.svelte";
import Convert from "../src/tools/Convert.svelte";
import Organize from "../src/tools/Organize.svelte";
import Security from "../src/tools/Security.svelte";

let bridge: ReturnType<typeof createFakeBridge>;

function file(path: string, kind: FileInfo["kind"] = "pdf"): FileInfo {
  const name = path.split("\\").pop()!;
  return { path, name, folder: "C:\\Belgeler", ext: name.slice(name.lastIndexOf(".")), kind, size: 10,
           exists: true, is_dir: kind === "folder" };
}

// What App does with a "drop" event from Python (lib/app.svelte.ts listen()).
function drop(page: typeof app.page, ...files: FileInfo[]) {
  app.page = page;
  app.drop(files);
}

const started = () => bridge.calls.filter(([name]) => name === "start").map(([, args]) => args);

describe("the tool pages", () => {
  beforeEach(() => {
    language.apply({ language: "tr", rtl: false, strings: {
      split_total_pages: "Toplam {count} sayfa", convert_drop_mismatch: "{name} bu türe uymuyor",
      batch_log_started: "Başladı: {path}", batch_success_count: "{succ} tamam, {errs} hata",
    } });
    bridge = createFakeBridge({ jobMs: 30, picks: ["C:\\Belgeler\\a.pdf", "C:\\Belgeler\\b.pdf"] });
    useBridge(bridge);
    app.settingsOpen = false;
    app.viewer = null;
  });

  it("split reads the page count and suggests a name with the range", async () => {
    render(Organize);
    drop("organize", file("C:\\Belgeler\\rapor.pdf"));
    await screen.findByText("Toplam 12 sayfa");
    expect(screen.getByLabelText("split_end")).toHaveValue(12);
    await waitFor(() => expect(bridge.calls).toContainEqual(["suggest_output", ["split", "C:\\Belgeler\\rapor.pdf", null]]));
    await fireEvent.click(screen.getAllByRole("button", { name: "split_btn" })[0]);
    await waitFor(() => expect(started()[0]).toEqual(["split", expect.objectContaining({ start: "1", end: "12" })]));
  });

  it("merge keeps the order of the list and can move files", async () => {
    render(Organize);
    await fireEvent.click(screen.getByRole("radio", { name: "txt_merge" }));
    await fireEvent.click(screen.getAllByRole("button", { name: "str_add" })[0]);
    const options = await screen.findAllByRole("option");
    const names = () => screen.getAllByRole("option").map((option) => option.querySelector("span")?.textContent);
    expect(names()).toEqual(["a.pdf", "b.pdf"]);
    await fireEvent.click(options[1]);
    await fireEvent.click(screen.getByRole("button", { name: "str_up" }));
    expect(names()).toEqual(["b.pdf", "a.pdf"]);
    await fireEvent.click(screen.getByRole("button", { name: "merge_btn" }));
    await waitFor(() => expect(started()[0]?.[1]).toMatchObject({ files: ["C:\\Belgeler\\b.pdf", "C:\\Belgeler\\a.pdf"] }));
  });

  it("security suggests a name for the chosen operation", async () => {
    render(Security);
    drop("security", file("C:\\Belgeler\\rapor.pdf"));
    await waitFor(() => expect(bridge.calls).toContainEqual(["suggest_output", ["security", "C:\\Belgeler\\rapor.pdf", "encrypt"]]));
    await fireEvent.click(screen.getByRole("radio", { name: "security_watermark" }));
    await waitFor(() => expect(bridge.calls).toContainEqual(["suggest_output", ["security", "C:\\Belgeler\\rapor.pdf", "watermark"]]));
    expect(screen.getByLabelText("security_watermark_text")).toHaveValue("GIZLI");
  });

  it("convert says so when a dropped file does not suit the mode", async () => {
    render(Convert);
    drop("convert", file("C:\\Belgeler\\sunum.pptx", "powerpoint"));
    await screen.findByText("sunum.pptx bu türe uymuyor");
    await fireEvent.click(screen.getByRole("radio", { name: "convert_ppt2pdf" }));
    drop("convert", file("C:\\Belgeler\\sunum.pptx", "powerpoint"));
    await waitFor(() => expect(screen.getByLabelText("convert_input_ppt")).toHaveValue("C:\\Belgeler\\sunum.pptx"));
  });

  it("advanced fills the metadata from the document", async () => {
    render(Advanced);
    drop("advanced", file("C:\\Belgeler\\rapor.pdf"));
    await fireEvent.click(screen.getByRole("radio", { name: "adv_metadata" }));
    await waitFor(() => expect(screen.getByLabelText("adv_meta_title")).toHaveValue("Faaliyet Raporu"));
  });

  it("batch logs the start and the count at the end", async () => {
    render(Batch);
    drop("batch", file("C:\\Belgeler\\Gelen", "folder"));
    await fireEvent.click(screen.getByRole("button", { name: "batch_start_btn" }));
    await screen.findByText(/Başladı: C:\\Belgeler\\Gelen/);
  });
});
