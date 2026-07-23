import { Download, FileUp, Play, RotateCcw, Square } from "lucide-react";
import type { KeyboardEvent } from "react";
import { IS_PRODUCTION, LANGGRAPH_API_URL, USES_DEV_PROXY } from "../config";
import { generatedPdfFromResult } from "../lib/generatedPdf";
import type { AgentRunSettings, AgentState } from "../types";

interface AgentConfigFormProps {
  settings: AgentRunSettings;
  onChange: <K extends keyof AgentRunSettings>(key: K, value: AgentRunSettings[K]) => void;
  disabled?: boolean;
  running: boolean;
  serverOnline: boolean;
  onStart: () => void;
  onStop: () => void;
  onReset: () => void;
  canReset?: boolean;
  result: AgentState | null;
  error: string | null;
}

function ToggleRow({
  label,
  hint,
  checked,
  onChange,
  disabled,
}: {
  label: string;
  hint?: string;
  checked: boolean;
  onChange: (value: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <label className="toggle-row">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        disabled={disabled}
      />
      <span>
        <strong>{label}</strong>
        {hint && <small>{hint}</small>}
      </span>
    </label>
  );
}

function messageContent(msg: { content?: unknown }): string {
  if (typeof msg.content === "string") return msg.content;
  if (Array.isArray(msg.content)) {
    return msg.content
      .map((part) => {
        if (typeof part === "string") return part;
        if (part && typeof part === "object" && "text" in part) {
          return String((part as { text?: string }).text ?? "");
        }
        return "";
      })
      .filter(Boolean)
      .join("\n");
  }
  return msg.content != null ? String(msg.content) : "";
}

function extractAnswer(result: AgentState | null): string {
  if (!result) return "";
  const messages = result.messages ?? [];
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const msg = messages[i];
    const type = (msg.type ?? "").toLowerCase();
    if (type === "ai" || type === "aimessage" || type.includes("ai")) {
      const text = messageContent(msg).trim();
      if (text) return text;
    }
  }
  return (result.task_plan_summary ?? "").trim();
}

export function AgentConfigForm({
  settings,
  onChange,
  disabled,
  running,
  serverOnline,
  onStart,
  onStop,
  onReset,
  canReset = true,
  result,
  error,
}: AgentConfigFormProps) {
  const answer = extractAnswer(result);
  const generatedPdf = generatedPdfFromResult(result);
  const isReadOnlyBlock =
    result?.agent_route === "reject_db_mutation" ||
    answer.includes("Database write blocked") ||
    answer.includes("Database mutation blocked") ||
    answer.includes("read-only access only");

  const readPdfFile = (file: File) => {
    if (file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf")) {
      onChange("pdf_data_base64", "");
      onChange("pdf_filename", "");
      onChange("pdf_analysis_enabled", false);
      return;
    }

    const reader = new FileReader();
    reader.onload = () => {
      const data = typeof reader.result === "string" ? reader.result : "";
      const base64 = data.includes(",") ? data.split(",")[1] : data;
      onChange("pdf_data_base64", base64);
      onChange("pdf_filename", file.name);
      onChange("pdf_analysis_enabled", true);
      onChange("pdf_summarize_only", true);
      onChange("user_input", `Summarize the uploaded PDF named ${file.name}.`);
    };
    reader.readAsDataURL(file);
  };

  const clearPdf = () => {
    onChange("pdf_data_base64", "");
    onChange("pdf_filename", "");
    onChange("pdf_analysis_enabled", false);
    onChange("pdf_summarize_only", false);
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!running && serverOnline && settings.user_input.trim()) onStart();
    }
  };

  return (
    <section className="panel">
      <div className="panel-title">
        <span>Ask Andromeda</span>
      </div>
      <p className="panel-desc">
        Calculate, search the web, analyze a PDF, find files, check location, or run a multi-step
        workflow.
      </p>

      <div className="composer">
        <textarea
          className="composer-input"
          value={settings.user_input}
          onChange={(e) => {
            onChange("user_input", e.target.value);
            onChange("pdf_summarize_only", false);
          }}
          onKeyDown={onKeyDown}
          placeholder="Type your message… (Enter to send, Shift+Enter for new line)"
          disabled={disabled}
          rows={3}
        />
        <div className="composer-actions">
          {!running ? (
            <button
              type="button"
              className="btn primary"
              disabled={!serverOnline || !settings.user_input.trim()}
              onClick={onStart}
            >
              <Play size={16} />
              Send
            </button>
          ) : (
            <button type="button" className="btn danger" onClick={onStop}>
              <Square size={16} />
              Stop
            </button>
          )}
          <button
            type="button"
            className="btn ghost"
            onClick={onReset}
            disabled={running || !canReset}
            title="Clear conversation"
          >
            <RotateCcw size={16} />
            Reset
          </button>
        </div>
      </div>

      {!serverOnline && (
        <p className="hint warn">
          {IS_PRODUCTION || !USES_DEV_PROXY ? (
            <>
              LangGraph backend is unreachable at <code>{LANGGRAPH_API_URL}</code>.
            </>
          ) : (
            <>
              Start the LangGraph server first: <code>./start.sh both</code>
            </>
          )}
        </p>
      )}
      {running && (
        <p className="hint running-hint">Working… watch the pipeline on the right for progress.</p>
      )}

      {error && (
        <div className="answer-box answer-error">
          <strong>Error</strong>
          <p>{error}</p>
        </div>
      )}

      {!error && answer && (
        <div
          className={`answer-box${isReadOnlyBlock ? " answer-warning" : ""}`}
          role={isReadOnlyBlock ? "alert" : undefined}
        >
          <strong>{isReadOnlyBlock ? "Not allowed — read-only" : "Answer"}</strong>
          <div className="answer-body">{answer}</div>
        </div>
      )}

      <h3 className="form-section-title">PDF analysis</h3>
      <div className="pdf-upload-row">
        <label>
          <span>Upload PDF</span>
          <input
            type="file"
            accept="application/pdf,.pdf"
            disabled={disabled}
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) readPdfFile(file);
            }}
          />
        </label>
        {settings.pdf_filename ? (
          <div className="pdf-file-status">
            <strong>
              <FileUp size={14} style={{ marginRight: 6, verticalAlign: "middle" }} />
              {settings.pdf_filename}
            </strong>
            <small>PDF mode stays active for follow-up questions this session.</small>
            <button type="button" className="btn small ghost" disabled={disabled} onClick={clearPdf}>
              Clear PDF
            </button>
          </div>
        ) : generatedPdf ? (
          <div className="pdf-file-status">
            <strong>
              <Download size={14} style={{ marginRight: 6, verticalAlign: "middle" }} />
              {generatedPdf.filename}
            </strong>
            <small>Generated by Andromeda for your request — download it here.</small>
            <a
              className="btn small primary"
              href={generatedPdf.downloadUrl}
              download={generatedPdf.filename}
            >
              <Download size={14} />
              Download PDF
            </a>
          </div>
        ) : (
          <div className="pdf-file-status">
            <strong>Andromeda sample PDF</strong>
            <small>Download a sample, or ask the agent to generate a report PDF.</small>
            <a className="btn small primary" href="/andromeda-agent.pdf" download="andromeda-agent.pdf">
              <Download size={14} />
              Download sample
            </a>
          </div>
        )}
      </div>

      <h3 className="form-section-title">Capabilities</h3>
      <div className="toggle-grid">
        <ToggleRow
          label="Enable web search"
          hint="Let the agent use DuckDuckGo for recent information."
          checked={settings.web_search_enabled}
          onChange={(v) => onChange("web_search_enabled", v)}
          disabled={disabled}
        />
        <ToggleRow
          label="Ask uploaded PDF"
          hint="Answer only from the uploaded PDF using RAG retrieval."
          checked={Boolean(settings.pdf_analysis_enabled && settings.pdf_data_base64)}
          onChange={(v) => {
            onChange("pdf_analysis_enabled", v);
            if (!v) onChange("pdf_summarize_only", false);
          }}
          disabled={disabled || !settings.pdf_data_base64}
        />
      </div>
    </section>
  );
}
