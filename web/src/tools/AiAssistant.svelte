<script lang="ts">
  import { onDestroy, onMount } from "svelte";
  import { api } from "../lib/bridge";
  import { app, openViewer, previewFile } from "../lib/app.svelte";
  import { t } from "../lib/i18n.svelte";
  import { Feedback, ToolRun } from "../lib/run.svelte";
  import FileField from "../components/FileField.svelte";
  import Icon from "../components/Icon.svelte";
  import Segmented from "../components/Segmented.svelte";
  import ToolLayout from "../components/ToolLayout.svelte";

  type Tab = "chat" | "summary";
  type SummaryMode = "kisa" | "detayli" | "ogrenci" | "toplanti" | "hukuki";

  interface ChatMessage {
    id: number;
    question: string;
    answer: string;
    found: boolean;
    usedLlm: boolean;
    sources: { page: number; quote: string; score?: number }[];
  }

  let input = $state("");
  let activeTab = $state<Tab>("chat");

  // Chat state
  let question = $state("");
  let asking = $state(false);
  let pendingQuestion = "";
  let chatHistory = $state<ChatMessage[]>([]);
  let chatCounter = 0;
  const chatFeedback = new Feedback(() => t("ai_section_chat"), () => t("ai_question_placeholder"));
  const chatRun = new ToolRun(chatFeedback, {
    done: (outcome) => {
      const details = (outcome.details || {}) as {
        answer?: string;
        found?: boolean;
        used_llm?: boolean;
        sources?: { page: number; quote: string; score?: number }[];
      };
      const answerText = details.answer ?? outcome.message;
      const found = details.found ?? true;
      const usedLlm = details.used_llm ?? false;
      const sources = details.sources ?? [];
      chatHistory.push({
        id: ++chatCounter,
        question: pendingQuestion,
        answer: answerText,
        found,
        usedLlm,
        sources,
      });
      pendingQuestion = "";
    },
    failed: () => {
      if (!question && pendingQuestion) {
        question = pendingQuestion;
      }
      pendingQuestion = "";
    },
    cancelled: () => {
      if (!question && pendingQuestion) {
        question = pendingQuestion;
      }
      pendingQuestion = "";
    },
  });

  // Summary state
  let summaryMode = $state<SummaryMode>("kisa");
  let summarizing = $state(false);
  let summaryText = $state("");
  let summaryPoints = $state<string[]>([]);
  let summarySources = $state<number[]>([]);
  let summaryUsedLlm = $state(false);
  let copied = $state(false);
  let saving = $state(false);

  const summaryFeedback = new Feedback(() => t("ai_section_summary"), () => t("ai_no_summary_yet"));
  const summaryRun = new ToolRun(summaryFeedback, {
    done: (outcome) => {
      const details = (outcome.details || {}) as {
        text?: string;
        points?: string[];
        sources?: number[];
        used_llm?: boolean;
      };
      summaryText = details.text ?? outcome.message;
      summaryPoints = details.points ?? [];
      summarySources = details.sources ?? [];
      summaryUsedLlm = details.used_llm ?? false;
    },
  });

  const saveFeedback = new Feedback(() => t("ai_mode_save"), () => "");
  const saveRun = new ToolRun(saveFeedback);

  async function setInput(path: string) {
    input = path;
    previewFile(path);
  }

  async function browseInput() {
    const [file] = await api().pick_files("pdf");
    if (file) await setInput(file.path);
  }

  async function askQuestion() {
    const q = question.trim();
    const source = input.trim();
    if (!q || !source || chatRun.busy || asking) return;
    asking = true;
    pendingQuestion = q;
    question = "";
    try {
      const started = await chatRun.start("ai", { input: source, mode: "ask", question: q });
      if (!started) {
        if (!question) question = pendingQuestion;
        pendingQuestion = "";
      }
    } catch {
      if (!question) question = pendingQuestion;
      pendingQuestion = "";
    } finally {
      asking = false;
    }
  }

  function handleKeyDown(event: KeyboardEvent) {
    if (event.key === "Enter" && (event.ctrlKey || !event.shiftKey)) {
      event.preventDefault();
      void askQuestion();
    }
  }

  function clearChat() {
    if (chatRun.busy) {
      chatRun.cancel();
    }
    chatHistory = [];
    chatFeedback.idle();
  }

  async function startSummary() {
    const source = input.trim();
    if (!source || summaryRun.busy || summarizing) return;
    summarizing = true;
    try {
      await summaryRun.start("ai", {
        input: source,
        mode: "summary",
        summary_mode: summaryMode,
      });
    } finally {
      summarizing = false;
    }
  }

  async function saveAsTxt() {
    const text = summaryText.trim();
    if (!text || saveRun.busy || saving) return;
    saving = true;
    try {
      const stem = input ? input.replace(/\.pdf$/i, "") : "belge";
      const suggested = `${stem}_ozet.txt`;
      const target = await api().pick_save("text", suggested);
      if (target) {
        await saveRun.start("ai", { mode: "save", format: "txt", text, output: target });
      }
    } finally {
      saving = false;
    }
  }

  async function saveAsPdf() {
    const text = summaryText.trim();
    if (!text || saveRun.busy || saving) return;
    saving = true;
    try {
      const stem = input ? input.replace(/\.pdf$/i, "") : "belge";
      const suggested = `${stem}_ozet.pdf`;
      const target = await api().pick_save("pdf", suggested);
      if (target) {
        await saveRun.start("ai", { mode: "save", format: "pdf", text, output: target });
      }
    } finally {
      saving = false;
    }
  }

  async function copySummary() {
    const text = summaryText.trim();
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      copied = true;
      setTimeout(() => {
        copied = false;
      }, 2000);
    } catch {
      // ignore
    }
  }

  function jumpToPage(pageNumber: number) {
    if (!input || typeof pageNumber !== "number" || isNaN(pageNumber)) return;
    previewFile(input.trim(), Math.max(0, pageNumber - 1));
  }

  function openPageInViewer(pageNumber: number) {
    if (!input || typeof pageNumber !== "number" || isNaN(pageNumber)) return;
    const source = input.trim();
    const pageIndex = Math.max(0, pageNumber - 1);
    previewFile(source, pageIndex);
    openViewer(source, pageIndex);
  }

  onMount(() =>
    app.acceptDrops("ai", (files) => {
      const pdf = files.find((file) => file.kind === "pdf");
      if (pdf) void setInput(pdf.path);
    })
  );

  onDestroy(() => {
    if (chatRun.busy) chatRun.cancel();
    if (summaryRun.busy) summaryRun.cancel();
    if (saveRun.busy) saveRun.cancel();
    chatRun.dispose();
    summaryRun.dispose();
    saveRun.dispose();
  });
</script>

<ToolLayout hint={t("hint_ai")}>
  <h2 class="section-title">{t("str_file_selection")}</h2>
  <div class="fields">
    <FileField
      id="ai-input"
      label={t("str_input_pdf")}
      button={t("str_browse")}
      bind:value={input}
      onbrowse={browseInput}
      oninput={(value) => previewFile(value.trim())}
    />
  </div>

  <div class="tabs">
    <Segmented
      label={t("txt_ai")}
      bind:value={activeTab}
      options={[
        { value: "chat", label: t("ai_tab_chat") },
        { value: "summary", label: t("ai_tab_summary") },
      ]}
    />
  </div>

  {#if activeTab === "chat"}
    <section class="chat-section" aria-label={t("ai_section_chat")}>
      <div class="chat-thread">
        {#if chatHistory.length === 0}
          <div class="empty-state">
            <Icon name="SPARK" size={32} />
            <p class="body-strong">{t("ai_tab_chat")}</p>
            <p class="small faint">{t("ai_no_chat_yet")}</p>
          </div>
        {:else}
          {#each chatHistory as item (item.id)}
            <div class="chat-entry">
              <div class="user-bubble">
                <span class="bubble-tag small">{t("ai_question_label")}</span>
                <p class="body selectable">{item.question}</p>
              </div>

              {#if !item.found}
                <div class="not-found-card card">
                  <div class="not-found-header">
                    <Icon name="INFO" size={16} />
                    <span class="body-strong">{t("ai_not_found_message")}</span>
                  </div>
                  <p class="small faint not-found-hint">{t("ai_not_found_hint")}</p>
                </div>
              {:else}
                <div class="assistant-card card">
                  <div class="card-meta">
                    <span class="body-strong">{t("ai_answer_title")}</span>
                    <span class="pill-badge small">{t(item.usedLlm ? "ai_badge_llm" : "ai_badge_extractive")}</span>
                  </div>
                  <p class="body answer-text selectable">{item.answer}</p>

                  {#if item.sources && item.sources.length > 0}
                    <div class="sources-box">
                      <p class="sources-title label">{t("ai_sources_title")}</p>
                      <div class="source-cards">
                        {#each item.sources as src, srcIdx (srcIdx + '-' + src.page)}
                          <div
                            class="source-card"
                            role="button"
                            tabindex="0"
                            onclick={() => jumpToPage(src.page)}
                            onkeydown={(e) => e.key === "Enter" && jumpToPage(src.page)}
                            title={t("ai_source_jump_title", { page: src.page })}
                          >
                            <div class="source-card-header">
                              <span class="source-page-tag small">{t("ai_source_card", { page: src.page })}</span>
                              <button
                                type="button"
                                class="jump-btn btn-ghost"
                                title={t("ai_source_open_viewer")}
                                onclick={(e) => {
                                  e.stopPropagation();
                                  openPageInViewer(src.page);
                                }}
                              >
                                <Icon name="OPEN" size={12} />
                                <span class="small">{t("ai_source_jump")}</span>
                              </button>
                            </div>
                            <p class="source-quote small faint">"{src.quote}"</p>
                          </div>
                        {/each}
                      </div>
                    </div>
                  {/if}
                </div>
              {/if}
            </div>
          {/each}
        {/if}
      </div>

      <div class="chat-composer">
        <label for="ai-question-input" class="label composer-label">{t("ai_question_label")}</label>
        <textarea
          id="ai-question-input"
          class="chat-input body"
          placeholder={t("ai_question_placeholder")}
          bind:value={question}
          onkeydown={handleKeyDown}
          rows="2"
        ></textarea>

        <div class="composer-toolbar">
          <div class="composer-buttons">
            <button
              type="button"
              class="btn btn-primary"
              disabled={!input.trim() || !question.trim() || chatRun.busy || asking}
              onclick={askQuestion}
            >
              <Icon name="SEND" size={13} />
              {t("ai_ask_btn")}
            </button>
            {#if chatRun.busy}
              <button
                type="button"
                class="btn btn-secondary"
                disabled={chatRun.cancelling}
                onclick={() => chatRun.cancel()}
              >
                {t(chatRun.cancelling ? "ai_cancelling" : "ai_cancel")}
              </button>
            {/if}
            {#if chatHistory.length > 0}
              <button type="button" class="btn btn-ghost" onclick={clearChat}>
                <Icon name="CLEAR" size={13} />
                {t("ai_clear_history")}
              </button>
            {/if}
          </div>

          {#if chatRun.busy}
            <div class="progress-wrap">
              <div
                class="progress-bar"
                role="progressbar"
                aria-valuemin="0"
                aria-valuemax="100"
                aria-valuenow={chatRun.percent}
              >
                <span class="bar-fill" style:width="{chatRun.percent}%"></span>
              </div>
              <p class="small faint ellipsis">{chatRun.note}</p>
            </div>
          {/if}
        </div>

        {#if chatFeedback.tone === "danger"}
          <p class="feedback-msg small error">{chatFeedback.message}</p>
        {/if}
      </div>
    </section>
  {:else}
    <section class="summary-section" aria-label={t("ai_section_summary")}>
      <div class="summary-controls panel-card">
        <p class="label">{t("ai_summary_mode_label")}</p>
        <div class="modes-segmented">
          <Segmented
            label={t("ai_summary_mode_label")}
            bind:value={summaryMode}
            options={[
              { value: "kisa", label: t("ai_mode_kisa") },
              { value: "detayli", label: t("ai_mode_detayli") },
              { value: "ogrenci", label: t("ai_mode_ogrenci") },
              { value: "toplanti", label: t("ai_mode_toplanti") },
              { value: "hukuki", label: t("ai_mode_hukuki") },
            ]}
          />
        </div>

        <div class="summary-action-row">
          <button
            type="button"
            class="btn btn-primary"
            disabled={!input.trim() || summaryRun.busy || summarizing}
            onclick={startSummary}
          >
            <Icon name="SPARK" size={13} />
            {t("ai_summarize_btn")}
          </button>
          {#if summaryRun.busy}
            <button
              type="button"
              class="btn btn-secondary"
              disabled={summaryRun.cancelling}
              onclick={() => summaryRun.cancel()}
            >
              {t(summaryRun.cancelling ? "ai_cancelling" : "ai_cancel")}
            </button>
          {/if}

          {#if summaryRun.busy}
            <div class="progress-wrap">
              <div
                class="progress-bar"
                role="progressbar"
                aria-valuemin="0"
                aria-valuemax="100"
                aria-valuenow={summaryRun.percent}
              >
                <span class="bar-fill" style:width="{summaryRun.percent}%"></span>
              </div>
              <p class="small faint ellipsis">{summaryRun.note}</p>
            </div>
          {/if}
        </div>

        {#if summaryFeedback.tone === "danger"}
          <p class="feedback-msg small error">{summaryFeedback.message}</p>
        {/if}
      </div>

      {#if summaryText}
        <div class="summary-output panel-card">
          <div class="summary-top-bar">
            <div class="summary-title-meta">
              <span class="body-strong">{t("ai_summary_result_label")}</span>
              <span class="pill-badge small">{t(summaryUsedLlm ? "ai_badge_llm" : "ai_badge_extractive")}</span>
            </div>
            <div class="summary-export-buttons">
              <button type="button" class="btn btn-secondary" onclick={copySummary}>
                <Icon name="DOCUMENT" size={12} />
                {t(copied ? "ai_copied" : "ai_copy")}
              </button>
              <button
                type="button"
                class="btn btn-secondary"
                disabled={!summaryText.trim() || saveRun.busy || saving}
                onclick={saveAsTxt}
              >
                {t("ai_save_txt")}
              </button>
              <button
                type="button"
                class="btn btn-secondary"
                disabled={!summaryText.trim() || saveRun.busy || saving}
                onclick={saveAsPdf}
              >
                {t("ai_save_pdf")}
              </button>
            </div>
          </div>

          {#if saveFeedback.output}
            <p class="feedback-msg small success">{saveFeedback.message}</p>
          {/if}

          <div class="summary-text body selectable">
            {summaryText}
          </div>

          {#if summaryPoints && summaryPoints.length > 0}
            <div class="summary-points-block">
              <p class="label">{t("ai_summary_points_label")}</p>
              <ul class="points-list">
                {#each summaryPoints as point, pIdx (pIdx + '-' + point)}
                  <li class="body small selectable">{point}</li>
                {/each}
              </ul>
            </div>
          {/if}

          {#if summarySources && summarySources.length > 0}
            <div class="summary-sources-block">
              <span class="label">{t("ai_summary_sources_label")}</span>
              <div class="source-pills">
                {#each summarySources as pNum, sIdx (sIdx + '-' + pNum)}
                  <button
                    type="button"
                    class="pill-btn small"
                    onclick={() => jumpToPage(pNum)}
                    title={t("ai_source_jump_title", { page: pNum })}
                  >
                    {t("ai_source_card", { page: pNum })}
                  </button>
                {/each}
              </div>
            </div>
          {/if}
        </div>
      {:else if !summaryRun.busy}
        <div class="empty-state">
          <Icon name="DOCUMENT" size={32} />
          <p class="body-strong">{t("ai_tab_summary")}</p>
          <p class="small faint">{t("ai_no_summary_yet")}</p>
        </div>
      {/if}
    </section>
  {/if}
</ToolLayout>

<style>
  .fields {
    margin-top: 14px;
  }
  .tabs {
    margin-top: 18px;
    margin-bottom: 16px;
  }
  .chat-section,
  .summary-section {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  .chat-thread {
    display: flex;
    flex-direction: column;
    gap: 16px;
    min-height: 180px;
  }
  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    padding: 36px 16px;
    color: var(--text-tertiary);
    gap: 8px;
    background: var(--surface-subtle);
    border: 1px dashed var(--border);
    border-radius: var(--radius);
  }
  .chat-entry {
    display: flex;
    flex-direction: column;
    gap: 10px;
    min-width: 0;
  }
  .user-bubble {
    align-self: flex-end;
    background: var(--accent-subtle);
    border: 1px solid var(--accent-border);
    border-radius: var(--radius) var(--radius) 2px var(--radius);
    padding: 10px 14px;
    max-width: 85%;
    overflow-wrap: break-word;
    word-break: break-word;
    min-width: 0;
  }
  .bubble-tag {
    color: var(--accent-text);
    display: block;
    margin-bottom: 2px;
  }
  .assistant-card {
    align-self: flex-start;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius) var(--radius) var(--radius) 2px;
    padding: 14px 16px;
    width: 100%;
    box-sizing: border-box;
    overflow-wrap: break-word;
    word-break: break-word;
    min-width: 0;
  }
  .card-meta {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 8px;
  }
  .pill-badge {
    background: var(--sunken);
    color: var(--text-secondary);
    padding: 2px 8px;
    border-radius: 12px;
  }
  .answer-text {
    line-height: 1.5;
    white-space: pre-wrap;
    overflow-wrap: break-word;
    word-break: break-word;
  }
  .not-found-card {
    background: var(--warning-bg);
    border: 1px solid var(--warning-border);
    padding: 14px 16px;
    border-radius: var(--radius);
  }
  .not-found-header {
    display: flex;
    align-items: center;
    gap: 8px;
    color: var(--warning);
  }
  .not-found-hint {
    margin-top: 6px;
    color: var(--text-secondary);
  }
  .sources-box {
    margin-top: 14px;
    padding-top: 12px;
    border-top: 1px solid var(--border-subtle);
  }
  .sources-title {
    margin-bottom: 8px;
    color: var(--text-secondary);
  }
  .source-cards {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 8px;
  }
  .source-card {
    background: var(--surface-subtle);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 8px 10px;
    cursor: pointer;
    transition: background 0.15s, border-color 0.15s;
    text-align: left;
    min-width: 0;
    overflow: hidden;
  }
  .source-card:hover {
    background: var(--hover);
    border-color: var(--border-strong);
  }
  .source-card:focus-visible {
    outline: 2px solid var(--focus-ring);
  }
  .source-card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 4px;
  }
  .source-page-tag {
    font-weight: 600;
    color: var(--accent-text);
  }
  .jump-btn {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 2px 6px;
    border-radius: var(--radius);
    border: none;
    background: transparent;
    cursor: pointer;
    color: var(--text-secondary);
  }
  .jump-btn:hover {
    background: var(--hover);
    color: var(--text);
  }
  .source-quote {
    margin: 0;
    line-height: 1.35;
    display: -webkit-box;
    -webkit-line-clamp: 3;
    line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
    overflow-wrap: break-word;
    word-break: break-word;
  }
  .chat-composer {
    margin-top: 8px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .composer-label {
    margin-bottom: 2px;
  }
  .chat-input {
    width: 100%;
    box-sizing: border-box;
    padding: 10px 12px;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    background: var(--field);
    color: var(--text);
    resize: vertical;
    font-family: inherit;
    line-height: 1.4;
  }
  .chat-input:focus {
    outline: none;
    border-color: var(--accent);
    box-shadow: 0 0 0 2px var(--focus-ring);
  }
  .composer-toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 10px;
  }
  .composer-buttons {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .progress-wrap {
    display: flex;
    align-items: center;
    gap: 10px;
    flex: 1 1 200px;
    max-width: 320px;
  }
  .progress-bar {
    flex: 1;
    height: 6px;
    border-radius: 3px;
    background: var(--sunken);
    overflow: hidden;
  }
  .bar-fill {
    display: block;
    height: 100%;
    background: var(--accent);
    transition: width 0.2s ease;
  }
  .summary-controls {
    padding: 16px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .modes-segmented {
    overflow-x: auto;
  }
  .summary-action-row {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
  }
  .summary-output {
    padding: 18px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    display: flex;
    flex-direction: column;
    gap: 14px;
    min-width: 0;
  }
  .summary-top-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 10px;
  }
  .summary-title-meta {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .summary-export-buttons {
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .summary-text {
    line-height: 1.6;
    white-space: pre-wrap;
    padding: 12px;
    background: var(--surface-subtle);
    border-radius: var(--radius);
    border: 1px solid var(--border-subtle);
    overflow-wrap: break-word;
    word-break: break-word;
    max-height: 500px;
    overflow-y: auto;
  }
  .summary-points-block {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .points-list {
    margin: 0;
    padding-inline-start: 20px;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .points-list li {
    overflow-wrap: break-word;
    word-break: break-word;
  }
  .summary-sources-block {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
    padding-top: 8px;
    border-top: 1px solid var(--border-subtle);
  }
  .source-pills {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
  }
  .pill-btn {
    background: var(--sunken);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 2px 10px;
    cursor: pointer;
    color: var(--accent-text);
    transition: background 0.15s;
  }
  .pill-btn:hover {
    background: var(--hover);
  }
  .feedback-msg {
    margin: 4px 0 0;
  }
  .feedback-msg.error {
    color: var(--danger);
  }
  .feedback-msg.success {
    color: var(--success);
  }
</style>
