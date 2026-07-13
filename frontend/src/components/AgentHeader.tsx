import {
  Activity,
  FileText,
  MapPin,
  Orbit,
  Radio,
  Sparkles,
  Wrench,
} from "lucide-react";
import type { ServerStatus } from "../hooks/useServerHealth";

interface AgentHeaderProps {
  serverStatus: ServerStatus;
  latencyMs: number | null;
  apiUrl: string;
  running: boolean;
}

export function AgentHeader({ serverStatus, latencyMs, apiUrl, running }: AgentHeaderProps) {
  return (
    <header className="agent-header">
      <div className="brand">
        <div className="brand-icon">
          <Orbit size={24} />
        </div>
        <div>
          <h1>Andromeda</h1>
          <p>Multi-tool LangGraph assistant for math, search, PDF, location, and Gmail</p>
        </div>
      </div>

      <div className="header-status">
        <div className={`status-pill ${serverStatus}`}>
          <Radio size={14} />
          <span>
            LangGraph{" "}
            {serverStatus === "online"
              ? "connected"
              : serverStatus === "offline"
                ? "offline"
                : "…"}
          </span>
          {latencyMs != null && <span className="muted">· {latencyMs}ms</span>}
        </div>
        {running && (
          <div className="status-pill running">
            <Activity size={14} className="spin" />
            <span>Agent running</span>
          </div>
        )}
        <div className="status-pill neutral">
          <span className="mono truncate">{apiUrl}</span>
        </div>
      </div>

      <div className="header-badges">
        <span className="badge">
          <Sparkles size={12} /> Multi-step routing
        </span>
        <span className="badge">
          <Wrench size={12} /> Tool orchestration
        </span>
        <span className="badge">
          <FileText size={12} /> PDF analysis
        </span>
        <span className="badge">
          <MapPin size={12} /> Live location
        </span>
      </div>
    </header>
  );
}
