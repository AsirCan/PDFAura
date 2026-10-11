import { beforeEach, describe, expect, it, vi } from "vitest";
import { emit, useBridge } from "../src/lib/bridge";
import { dialogs } from "../src/lib/dialog.svelte";
import { createFakeBridge } from "../src/lib/fake-bridge";
import { language } from "../src/lib/i18n.svelte";
import { Feedback, ToolRun } from "../src/lib/run.svelte";

describe("running a tool", () => {
  beforeEach(() => {
    dialogs.answer(false);
  });

  it("goes from busy through progress to done", async () => {
    vi.useFakeTimers();
    const bridge = useBridge(createFakeBridge({ jobMs: 400 }));
    const feedback = new Feedback();
    const run = new ToolRun(feedback);
    expect(await run.start("compress", { input: "a.pdf", output: "b.pdf" })).toBe(true);
    expect(run.busy).toBe(true);
    expect(feedback.tone).toBe("busy");
    vi.advanceTimersByTime(250);
    expect(run.percent).toBe(66);
    vi.advanceTimersByTime(200);
    expect(run.busy).toBe(false);
    expect(run.finished).toBe(true);
    expect(feedback.tone).toBe("success");
    expect(feedback.output).toBe("b.pdf");
    expect(bridge.calls.map(([name]) => name)).toEqual(["check", "start"]);
    vi.useRealTimers();
  });

  it("shows what to fix instead of starting", async () => {
    useBridge(createFakeBridge({ problem: "Bir PDF seçin" }));
    const feedback = new Feedback();
    const run = new ToolRun(feedback);
    expect(await run.start("compress", {})).toBe(false);
    expect(feedback.tone).toBe("danger");
    expect(feedback.message).toBe("Bir PDF seçin");
    expect(run.busy).toBe(false);
  });

  it("can be cancelled", async () => {
    useBridge(createFakeBridge({ jobMs: 10_000 }));
    const feedback = new Feedback();
    const run = new ToolRun(feedback);
    await run.start("compress", {});
    run.cancel();
    await vi.waitFor(() => expect(feedback.tone).toBe("warning"));
    expect(run.busy).toBe(false);
    expect(run.cancelling).toBe(false);
  });

  it("ignores events of other jobs", async () => {
    useBridge(createFakeBridge({ jobMs: 10_000 }));
    const run = new ToolRun(new Feedback());
    await run.start("compress", {});
    emit("job", { id: 999, type: "cancelled" });
    expect(run.busy).toBe(true);
    run.cancel();
  });

  it("asks before replacing a file the app suggested", async () => {
    language.apply({ language: "tr", rtl: false, strings: { overwrite_body: "{path} var" } });
    const bridge = useBridge(createFakeBridge({ existing: ["C:\\rapor.pdf"] }));
    const run = new ToolRun(new Feedback());
    const started = run.start("compress", { output: "C:\\rapor.pdf" }, { askOverwrite: true });
    await vi.waitFor(() => expect(dialogs.open?.body).toContain("C:\\rapor.pdf"));
    dialogs.answer(false);
    expect(await started).toBe(false);
    expect(bridge.calls.some(([name]) => name === "start")).toBe(false);
  });

  it("replaces the file once the user agrees", async () => {
    const bridge = useBridge(createFakeBridge({ existing: ["C:\\rapor.pdf"], jobMs: 10_000 }));
    const run = new ToolRun(new Feedback());
    const started = run.start("compress", { output: "C:\\rapor.pdf" }, { askOverwrite: true });
    await vi.waitFor(() => expect(dialogs.open).not.toBeNull());
    dialogs.answer(true);
    expect(await started).toBe(true);
    expect(bridge.calls.filter(([name]) => name === "start")).toHaveLength(1);
    run.cancel();
  });

  it("does not ask when nothing is there yet", async () => {
    const bridge = useBridge(createFakeBridge({ existing: ["C:\\baska.pdf"], jobMs: 10_000 }));
    const run = new ToolRun(new Feedback());
    expect(await run.start("compress", { output: "C:\\rapor.pdf" }, { askOverwrite: true })).toBe(true);
    expect(dialogs.open).toBeNull();
    expect(bridge.calls.map(([name]) => name)).toEqual(["check", "existing_target", "start"]);
    run.cancel();
  });
});
