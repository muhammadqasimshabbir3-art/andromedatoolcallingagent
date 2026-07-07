import { IS_PRODUCTION, LANGGRAPH_API_URL, USES_DEV_PROXY } from "../config";
import type { AgentRunSettings } from "../types";

interface AgentConfigFormProps {
  settings: AgentRunSettings;
  onChange: <K extends keyof AgentRunSettings>(key: K, value: AgentRunSettings[K]) => void;
  disabled?: boolean;
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

export function AgentConfigForm({ settings, onChange, disabled }: AgentConfigFormProps) {
  const readPdfFile = (file: File) => {
    if (file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf")) {
      onChange("pdf_data_base64", "");
      onChange("pdf_filename", "");
      onChange("pdf_analysis_enabled", false);
      return;
    }

    const reader = new FileReader();
    reader.onload = () => {
      const result = typeof reader.result === "string" ? reader.result : "";
      const base64 = result.includes(",") ? result.split(",")[1] : result;
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

  return (
    <section className="panel channel-form">
      <div className="panel-title">
        <span>🤖 Andromeda Agent Input</span>
      </div>
      <p className="panel-desc">
        Enter your request below. The agent supports multi-step workflows like calculator operations, local file search, web search, PDF generation, and email.
      </p>

      <h3 className="form-section-title">Request</h3>
      <div className="form-grid">
        <label style={{ gridColumn: '1 / -1' }}>
          <span>User Input</span>
          <textarea
            value={settings.user_input}
            onChange={(e) => {
              onChange("user_input", e.target.value);
              onChange("pdf_summarize_only", false);
            }}
            placeholder="e.g. What is log(1000) + sin(30)?"
            disabled={disabled}
            rows={4}
            style={{ width: '100%', resize: 'vertical' }}
          />
        </label>
      </div>

      <h3 className="form-section-title">PDF Analysis</h3>
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
        {settings.pdf_filename && (
          <div className="pdf-file-status">
            <strong>{settings.pdf_filename}</strong>
            <small>PDF mode is active for follow-up questions.</small>
            <button type="button" className="btn small ghost" disabled={disabled} onClick={clearPdf}>
              Clear PDF
            </button>
          </div>
        )}
      </div>

      <div className="toggle-grid">
        <ToggleRow
          label="Enable Web Search"
          hint="Allow the agent to use DuckDuckGo to search for recent information."
          checked={settings.web_search_enabled}
          onChange={(v) => onChange("web_search_enabled", v)}
          disabled={disabled}
        />
        <ToggleRow
          label="Ask Uploaded PDF"
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

interface RunControlsProps {
  running: boolean;
  serverOnline: boolean;
  onStart: () => void;
  onStop: () => void;
}

export function RunControls({ running, serverOnline, onStart, onStop }: RunControlsProps) {
  return (
    <section className="panel run-controls">
      <div className="panel-title">
        <span>🚀 Execution</span>
      </div>
      <div className="button-row">
        {!running ? (
          <button
            type="button"
            className="btn primary start-btn"
            disabled={!serverOnline}
            onClick={onStart}
          >
            ▶️ Send Message
          </button>
        ) : (
          <button type="button" className="btn danger stop-btn" onClick={onStop}>
            ⏹️ Stop Agent
          </button>
        )}
      </div>
      {!serverOnline && (
        <p className="hint warn">
          {IS_PRODUCTION || !USES_DEV_PROXY ? (
            <>
              LangGraph backend is unreachable at <code>{LANGGRAPH_API_URL}</code>. Check the Railway
              deployment, then refresh the connection panel.
            </>
          ) : (
            <>
              Start the LangGraph server first: <code>./start.sh both</code>
            </>
          )}
        </p>
      )}
      {running && (
        <p className="hint running-hint">🔄 Agent is working — watch the pipeline below for live progress…</p>
      )}
    </section>
  );
}
