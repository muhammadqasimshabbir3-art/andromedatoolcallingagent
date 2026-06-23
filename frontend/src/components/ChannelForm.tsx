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
            onChange={(e) => onChange("user_input", e.target.value)}
            placeholder="e.g. What is log(1000) + sin(30)?"
            disabled={disabled}
            rows={4}
            style={{ width: '100%', resize: 'vertical' }}
          />
        </label>
      </div>

      <div className="toggle-grid">
        <ToggleRow
          label="Enable Web Search"
          hint="Allow the agent to use DuckDuckGo to search for recent information."
          checked={settings.web_search_enabled}
          onChange={(v) => onChange("web_search_enabled", v)}
          disabled={disabled}
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
          Start the LangGraph server first: <code>./start.sh both</code>
        </p>
      )}
      {running && (
        <p className="hint running-hint">🔄 Agent is working — watch the pipeline below for live progress…</p>
      )}
    </section>
  );
}
