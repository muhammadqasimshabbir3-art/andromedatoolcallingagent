import { useMemo, useState } from "react";
import { MessageSquare } from "lucide-react";
import type { AgentState } from "../types";

interface ResultsDashboardProps {
  result: AgentState | null;
  error: string | null;
}

export function ResultsDashboard({ result, error }: ResultsDashboardProps) {
  const [tab, setTab] = useState("response");

  const tabs = useMemo(
    () => [
      { id: "response", label: "Final Response" },
      { id: "messages", label: `Messages (${result?.messages?.length ?? 0})` },
    ],
    [result],
  );

  if (error) {
    return (
      <section className="panel results-panel error-panel">
        <h3>Workflow Error</h3>
        <p>{error}</p>
      </section>
    );
  }

  if (!result || !result.messages || result.messages.length === 0) {
    return (
      <section className="panel results-panel empty-panel">
        <MessageSquare size={28} />
        <h3>Results will appear here</h3>
        <p>Start an agent run to see the responses, calculations, tool usage, and reports.</p>
      </section>
    );
  }

  const latestMessage = result.messages[result.messages.length - 1];
  const hasToolCalls = Array.isArray(latestMessage?.tool_calls) && latestMessage.tool_calls.length > 0;

  return (
    <section className="panel results-panel">
      <div className="results-header">
        <div>
          <h3>Execution Dashboard</h3>
          <p>
            {result.task_plan_summary && <strong>{result.task_plan_summary}</strong>}
            {result.agent_route && <> · Route: {result.agent_route}</>}
          </p>
        </div>
      </div>

      <div className="metrics-grid">
        <Metric label="Messages" value={String(result.messages.length)} />
        <Metric label="Route" value={result.agent_route ?? "call_model"} />
        <Metric label="Tools Used" value={hasToolCalls ? String(latestMessage.tool_calls!.length) : "0"} />
      </div>

      <div className="tab-bar">
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            className={`tab ${tab === t.id ? "active" : ""}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="tab-content">
        {tab === "response" && (
          <div className="summary-box" style={{ whiteSpace: "pre-wrap", padding: "16px", background: "var(--bg-secondary)", borderRadius: "8px" }}>
            {latestMessage?.content || "No text content generated."}
            {hasToolCalls && (
              <div style={{ marginTop: '16px', paddingTop: '16px', borderTop: '1px solid var(--border)' }}>
                <strong>🔧 Tools Used:</strong>
                <ul style={{ marginTop: '8px' }}>
                  {latestMessage.tool_calls!.map((tc, idx) => (
                    <li key={idx}><strong>{tc.name}</strong>: {JSON.stringify(tc.args)}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
        
        {tab === "messages" && (
          <div className="table-wrap">
            <table style={{ width: "100%", textAlign: "left" }}>
              <thead>
                <tr>
                  <th>Type</th>
                  <th>Content</th>
                </tr>
              </thead>
              <tbody>
                {result.messages.map((msg, i) => (
                  <tr key={i}>
                    <td><strong style={{ textTransform: "capitalize" }}>{msg.type || "unknown"}</strong></td>
                    <td style={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}>{msg.content}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric-card">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
