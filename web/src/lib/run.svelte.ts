// Running a tool from a page, the same way for every tool -- the web twin
// of ToolRun in src/gui/helpers.py: check the input, ask before replacing a
// file the app suggested, start, follow progress, and end in exactly one of
// done / failed / cancelled, shown in the result panel.
import { api, on } from "./bridge";
import { dialogs } from "./dialog.svelte";
import { t } from "./i18n.svelte";
import type { JobEvent, Outcome, Params } from "./types";

export type Tone = "neutral" | "info" | "busy" | "success" | "warning" | "danger";

/** The result panel's state (InlineFeedback in helpers.py). */
export class Feedback {
  tone = $state<Tone>("neutral");
  badge = $state("");
  title = $state("");
  message = $state("");
  output = $state<string | null>(null);

  constructor(title?: string, message?: string) {
    if (title !== undefined) this.info(title, message ?? "");
    else this.idle();
  }

  private set(tone: Tone, badge: string, title: string, message: string, output: string | null = null) {
    this.tone = tone;
    this.badge = t(badge);
    this.title = title;
    this.message = message;
    this.output = output;
  }

  idle(title?: string, message?: string) {
    this.set("neutral", "feedback_ready_badge", title ?? t("feedback_ready_title"), message ?? t("feedback_ready_body"));
  }
  busy(message: string) {
    this.set("busy", "feedback_busy_badge", t("feedback_busy_title"), message);
  }
  success(title: string, message: string, output: string | null = null) {
    this.set("success", "feedback_done_badge", title, message, output);
  }
  warning(title: string, message: string, output: string | null = null) {
    this.set("warning", "feedback_warning_badge", title, message, output);
  }
  error(title: string, message: string) {
    this.set("danger", "feedback_error_badge", title, message);
  }
  info(title: string, message: string) {
    this.set("info", "feedback_info_badge", title, message);
  }
  cancelled() {
    this.set("warning", "perf_cancelled_badge", t("perf_cancelled"), t("perf_cancelled_msg"));
  }
  show(outcome: Outcome) {
    if (outcome.tone === "success") this.success(outcome.title, outcome.message, outcome.output);
    else if (outcome.tone === "warning") this.warning(outcome.title, outcome.message, outcome.output);
    else if (outcome.tone === "error") this.error(outcome.title, outcome.message);
    else this.info(outcome.title, outcome.message);
  }
}

export interface RunHooks {
  /** Replaces the footer's progress display (the batch log keeps every line). */
  progress?: (current: number, total: number, message: string) => void;
  done?: (outcome: Outcome) => void;
  failed?: (title: string, message: string) => void;
  cancelled?: () => void;
}

export class ToolRun {
  busy = $state(false);
  percent = $state(0);
  note = $state("");
  cancellable = $state(false);
  cancelling = $state(false);
  /** The bar stays full, in the success colour, after a run that worked. */
  finished = $state(false);
  feedback: Feedback;
  private job: number | null = null;
  private stop: (() => void) | null = null;

  constructor(feedback: Feedback, private hooks: RunHooks = {}) {
    this.feedback = feedback;
  }

  /** Check, ask before replacing a suggested output, then start. False if
   * nothing was started. */
  async start(tool: string, params: Params, { askOverwrite = false } = {}): Promise<boolean> {
    if (this.busy) return false;
    const bridge = api();
    const problem = await bridge.check(tool, params);
    if (problem) {
      this.feedback.error(t("str_error"), problem);
      return false;
    }
    if (askOverwrite) {
      const existing = await bridge.existing_target(tool, params);
      if (existing) {
        const replace = await dialogs.ask({
          title: t("overwrite_title"), body: t("overwrite_body", { path: existing }),
          confirm: t("overwrite_replace"), cancel: t("str_cancel"), danger: true,
        });
        if (!replace) return false;
      }
    }
    this.stop?.();
    this.stop = on("job", (event) => this.event(event));
    const started = await bridge.start(tool, params);
    if (started.problem || started.job === undefined) {
      this.stop();
      this.feedback.error(t("str_error"), started.problem ?? "");
      return false;
    }
    this.job = started.job;
    this.busy = true;
    this.finished = false;
    this.percent = 0;
    this.note = "0%";
    this.cancellable = Boolean(started.cancellable);
    this.cancelling = false;
    this.feedback.busy(started.busy ?? t("str_processing"));
    return true;
  }

  cancel() {
    if (this.job === null || this.cancelling) return;
    this.cancelling = true;
    void api().cancel(this.job);
  }

  private event(event: JobEvent) {
    if (event.id !== this.job) return;
    if (event.type === "progress") {
      if (this.hooks.progress) {
        this.hooks.progress(event.current, event.total, event.message);
        return;
      }
      const pct = Math.floor((event.current / Math.max(1, event.total)) * 100);
      this.percent = pct;
      const message = event.message.length < 48 ? event.message : `${event.message.slice(0, 45)}...`;
      this.note = message ? `${pct}%  ·  ${message}` : `${pct}%`;
      return;
    }
    this.end();
    if (event.type === "done") {
      this.finished = true;
      this.percent = 100;
      this.note = "100%";
      this.feedback.show(event.outcome);
      this.hooks.done?.(event.outcome);
    } else if (event.type === "failed") {
      this.feedback.error(event.title, event.message);
      this.hooks.failed?.(event.title, event.message);
    } else {
      this.feedback.cancelled();
      this.hooks.cancelled?.();
    }
  }

  private end() {
    this.busy = false;
    this.cancellable = false;
    this.cancelling = false;
    this.job = null;
    this.note = "";
    this.percent = 0;
    this.stop?.();
    this.stop = null;
  }

  dispose() {
    this.stop?.();
    this.stop = null;
  }
}
