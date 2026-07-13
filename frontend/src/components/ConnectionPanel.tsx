import { Loader2, RefreshCw } from "lucide-react";
import { useState } from "react";
import { ConnectionDiagnostic } from "./ConnectionDiagnostic";
import type { ServerStatus } from "../hooks/useServerHealth";

interface ConnectionPanelProps {
  status: ServerStatus;
  onRefresh: () => void;
}

export function ConnectionPanel({ status, onRefresh }: ConnectionPanelProps) {
  const [diagRun, setDiagRun] = useState(false);
  const online = status === "online";
  const checking = status === "checking";

  return (
    <aside className="panel connection-panel connection-panel-compact">
      <div className="backend-status-row">
        <div className="backend-status-label">
          <span
            className={`status-light ${online ? "online" : checking ? "checking" : "offline"}`}
            aria-hidden
          />
          <span className="backend-status-text">
            {checking ? "Checking…" : online ? "Connected" : "Offline"}
          </span>
        </div>
        <button type="button" className="icon-btn" onClick={onRefresh} title="Refresh connection">
          {checking ? <Loader2 size={14} className="spin" /> : <RefreshCw size={14} />}
        </button>
      </div>

      {!online && !checking && (
        <div className="deploy-note" style={{ marginTop: "0.75rem" }}>
          <button
            type="button"
            className="btn ghost small"
            onClick={() => setDiagRun(true)}
            disabled={diagRun}
          >
            Run diagnostic
          </button>
          <ConnectionDiagnostic run={diagRun} />
        </div>
      )}
    </aside>
  );
}
