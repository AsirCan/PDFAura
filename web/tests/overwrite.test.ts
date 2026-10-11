// Issue #28: a path picked in the save dialog stayed picked. Picking A's
// output and then choosing B wrote B's result over A's file, and in Advanced
// the OCR text went over the PDF picked for the signature, without a word.
// Every overwrite of a file on disk now follows either the save dialog (for
// that input and mode, once) or the in-window question.
import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { beforeEach, describe, expect, it } from "vitest";
import { useBridge } from "../src/lib/bridge";
import { app } from "../src/lib/app.svelte";
import { dialogs } from "../src/lib/dialog.svelte";
import { createFakeBridge } from "../src/lib/fake-bridge";
import { language } from "../src/lib/i18n.svelte";
import type { FileInfo } from "../src/lib/types";
import Advanced from "../src/tools/Advanced.svelte";
import Compress from "../src/tools/Compress.svelte";
import Security from "../src/tools/Security.svelte";

const DIR = "C:\\Belgeler\\";
let bridge: ReturnType<typeof createFakeBridge>;

function pdf(name: string): FileInfo {
  return { path: DIR + name, name, folder: "C:\\Belgeler", ext: ".pdf", kind: "pdf", size: 10, exists: true,
           is_dir: false };
}

function drop(page: typeof app.page, file: FileInfo) {
  app.page = page;
  app.drop([file]);
}

function setUp(existing: string[] = []) {
  bridge = useBridge(createFakeBridge({ jobMs: 20, existing: existing.map((name) => DIR + name) }));
}

const started = () => bridge.calls.filter(([name]) => name === "start").map(([, args]) => args[1] as Record<string, unknown>);
const asked = () => bridge.calls.filter(([name]) => name === "existing_target").length;

async function saveAs() {
  const picks = bridge.calls.filter(([name]) => name === "pick_save").length;
  await fireEvent.click(screen.getByRole("button", { name: "str_save_as" }));
  await waitFor(() => expect(bridge.calls.filter(([name]) => name === "pick_save")).toHaveLength(picks + 1));
}

/** Click the tool's button and wait until the run is over. */
async function runTool(button: string, tool: string) {
  const runs = started().length;
  await fireEvent.click(screen.getByRole("button", { name: button }));
  await waitFor(() => expect(started()).toHaveLength(runs + 1));
  await waitFor(() => expect(screen.getAllByText(`${tool} bitti`).length).toBeGreaterThan(0));
}

describe("replacing a file", () => {
  beforeEach(() => {
    language.apply({ language: "tr", rtl: false, strings: {} });
    dialogs.answer(false);
    app.settingsOpen = false;
    app.viewer = null;
  });

  it("does not send B's result to the path picked for A", async () => {
    setUp(["A_compress.pdf"]);
    render(Compress);
    drop("compress", pdf("A.pdf"));
    await waitFor(() => expect(screen.getByLabelText("str_output_pdf")).toHaveValue(`${DIR}A_compress.pdf`));
    await saveAs();
    await runTool("compress_btn", "compress");
    expect(started()[0]).toMatchObject({ input: `${DIR}A.pdf`, output: `${DIR}A_compress.pdf` });

    drop("compress", pdf("B.pdf"));
    await waitFor(() => expect(screen.getByLabelText("str_output_pdf")).toHaveValue(`${DIR}B_compress.pdf`));
    await runTool("compress_btn", "compress");
    expect(started()[1]).toMatchObject({ input: `${DIR}B.pdf`, output: `${DIR}B_compress.pdf` });
  });

  it("asks again on the second run to the picked path", async () => {
    setUp(["A_compress.pdf"]);
    render(Compress);
    drop("compress", pdf("A.pdf"));
    await waitFor(() => expect(screen.getByLabelText("str_output_pdf")).toHaveValue(`${DIR}A_compress.pdf`));
    await saveAs();
    // The save dialog has just asked about this file.
    await runTool("compress_btn", "compress");
    expect(asked()).toBe(0);

    await fireEvent.click(screen.getByRole("button", { name: "compress_btn" }));
    await waitFor(() => expect(dialogs.open?.title).toBe("overwrite_title"));
    dialogs.answer(false);
    await waitFor(() => expect(asked()).toBe(1));
    expect(started()).toHaveLength(1);
  });

  it("asks about a path typed over the picked one", async () => {
    setUp(["elle.pdf"]);
    render(Compress);
    drop("compress", pdf("A.pdf"));
    await waitFor(() => expect(screen.getByLabelText("str_output_pdf")).toHaveValue(`${DIR}A_compress.pdf`));
    await saveAs();
    await fireEvent.input(screen.getByLabelText("str_output_pdf"), { target: { value: `${DIR}elle.pdf` } });
    await fireEvent.click(screen.getByRole("button", { name: "compress_btn" }));
    await waitFor(() => expect(dialogs.open?.body).toBe("overwrite_body"));
    dialogs.answer(false);
    await waitFor(() => expect(dialogs.open).toBeNull());
    expect(started()).toEqual([]);
  });

  it("asks when the input was typed after the output was picked", async () => {
    setUp(["A_compress.pdf"]);
    render(Compress);
    drop("compress", pdf("A.pdf"));
    await waitFor(() => expect(screen.getByLabelText("str_output_pdf")).toHaveValue(`${DIR}A_compress.pdf`));
    await saveAs();
    await fireEvent.input(screen.getByLabelText("str_input_pdf"), { target: { value: `${DIR}B.pdf` } });
    await fireEvent.click(screen.getByRole("button", { name: "compress_btn" }));
    await waitFor(() => expect(dialogs.open?.title).toBe("overwrite_title"));
    dialogs.answer(false);
    await waitFor(() => expect(dialogs.open).toBeNull());
    expect(started()).toEqual([]);
  });

  it("keeps a path picked before the input was chosen", async () => {
    setUp();
    render(Compress);
    await saveAs();
    expect(screen.getByLabelText("str_output_pdf")).toHaveValue(`${DIR}cikti.pdf`);
    drop("compress", pdf("A.pdf"));
    await waitFor(() => expect(screen.getByLabelText("str_input_pdf")).toHaveValue(`${DIR}A.pdf`));
    await runTool("compress_btn", "compress");
    expect(started()[0]).toMatchObject({ input: `${DIR}A.pdf`, output: `${DIR}cikti.pdf` });
    expect(asked()).toBe(0);
  });

  it("advanced: the OCR text does not go over the PDF picked for the signature", async () => {
    setUp(["rapor_advanced_signature.pdf"]);
    render(Advanced);
    drop("advanced", pdf("rapor.pdf"));
    await fireEvent.click(screen.getByRole("radio", { name: "adv_signature" }));
    await waitFor(() => expect(screen.getByLabelText("str_output_dir_file"))
      .toHaveValue(`${DIR}rapor_advanced_signature.pdf`));
    await saveAs();
    await runTool("str_start", "advanced");
    expect(started()[0]).toMatchObject({ mode: "signature", output: `${DIR}rapor_advanced_signature.pdf` });

    await fireEvent.click(screen.getByRole("radio", { name: "adv_ocr" }));
    await waitFor(() => expect(screen.getByLabelText("str_output_dir_file"))
      .toHaveValue(`${DIR}rapor_advanced_ocr.pdf`));
    await runTool("str_start", "advanced");
    expect(started()[1]).toMatchObject({ mode: "ocr", output: `${DIR}rapor_advanced_ocr.pdf` });

    // Back to the signature: its path is still there, and asked about now.
    await fireEvent.click(screen.getByRole("radio", { name: "adv_signature" }));
    expect(screen.getByLabelText("str_output_dir_file")).toHaveValue(`${DIR}rapor_advanced_signature.pdf`);
    await fireEvent.click(screen.getByRole("button", { name: "str_start" }));
    await waitFor(() => expect(dialogs.open?.title).toBe("overwrite_title"));
    dialogs.answer(false);
    await waitFor(() => expect(dialogs.open).toBeNull());
    expect(started()).toHaveLength(2);
  });

  it("security: the watermark does not replace the file picked for encryption", async () => {
    setUp(["rapor_security_encrypt.pdf"]);
    render(Security);
    drop("security", pdf("rapor.pdf"));
    await waitFor(() => expect(screen.getByLabelText("str_output_pdf"))
      .toHaveValue(`${DIR}rapor_security_encrypt.pdf`));
    await saveAs();
    await runTool("str_apply", "security");
    expect(started()[0]).toMatchObject({ mode: "encrypt", output: `${DIR}rapor_security_encrypt.pdf` });

    await fireEvent.click(screen.getByRole("radio", { name: "security_watermark" }));
    await waitFor(() => expect(screen.getByLabelText("str_output_pdf"))
      .toHaveValue(`${DIR}rapor_security_watermark.pdf`));
    await runTool("str_apply", "security");
    expect(started()[1]).toMatchObject({ mode: "watermark", output: `${DIR}rapor_security_watermark.pdf` });
  });
});
