import { useState } from "react";
import { Loader2, RefreshCw, Server, Wifi, WifiOff } from "lucide-react";
import { ConnectionDiagnostic } from "./ConnectionDiagnostic";
import type { ServerStatus } from "../hooks/useServerHealth";

interface ConnectionPanelProps {
  status: ServerStatus;
  latencyMs: number | null;
  apiUrl: string;
  assistantId: string;
  threadId: string | null;
  runId: string | null;
  onRefresh: () => void;
}

export function ConnectionPanel({
  status,
  latencyMs,
  apiUrl,
  assistantId,
  threadId,
  runId,
  onRefresh,
}: ConnectionPanelProps) {
  const [diagRun, setDiagRun] = useState(false);

  return (
    <aside className="panel connection-panel">
      <div className="panel-title">
        <Server size={16} />
        <span>Backend</span>
        <button type="button" className="icon-btn" onClick={onRefresh} title="Refresh connection">
          <RefreshCw size={14} />
        </button>
      </div>

      <div className="connection-grid">
        <div className="connection-row">
          <span>API</span>
          <code className="mono">{apiUrl}</code>
        </div>
        <div className="connection-row">
          <span>Graph</span>
          <code className="mono">{assistantId}</code>
        </div>
        <div className="connection-row">
          <span>Health</span>
          <span className={`health ${status}`}>
            {status === "checking" && <Loader2 size={14} className="spin" />}
            {status === "online" && <Wifi size={14} />}
            {status === "offline" && <WifiOff size={14} />}
            {status}
            {latencyMs != null ? ` (${latencyMs}ms)` : ""}
          </span>
        </div>

        {threadId && (
          <div className="connection-row">
            <span>Thread</span>
            <code className="mono">{threadId.slice(0, 12)}…</code>
          </div>
        )}
        {runId && (
          <div className="connection-row">
            <span>Run</span>
            <code className="mono">{runId.slice(0, 12)}…</code>
          </div>
        )}
      </div>

      {status === "offline" && (
        <div className="deploy-note">
          <strong>Connection help</strong>
          <p>
            The UI could not reach the LangGraph API. Run a diagnostic to see whether env vars,
            network, or CORS is blocking the request.
          </p>
          <button
            type="button"
            className="btn ghost"
            onClick={() => setDiagRun(true)}
            disabled={diagRun}
          >
            Run connection diagnostic
          </button>
        </div>
      )}

      <ConnectionDiagnostic run={diagRun} />
    </aside>
  );
}
