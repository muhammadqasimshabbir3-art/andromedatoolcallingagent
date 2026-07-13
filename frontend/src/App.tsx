import { useCallback, useState } from "react";
import { AgentHeader } from "./components/AgentHeader";
import { AgentConfigForm } from "./components/AgentConfigForm";
import { ConnectionPanel } from "./components/ConnectionPanel";
import { WorkflowPipeline } from "./components/WorkflowPipeline";
import { useAgentRun } from "./hooks/useAgentRun";
import { useServerHealth } from "./hooks/useServerHealth";
import { loadRunSettings, saveRunSettings } from "./lib/settingsStorage";
import type { AgentRunSettings } from "./types";

export default function App() {
  const health = useServerHealth();
  const agent = useAgentRun();
  const [settings, setSettings] = useState<AgentRunSettings>(loadRunSettings);

  const updateSetting = useCallback(
    <K extends keyof AgentRunSettings>(key: K, value: AgentRunSettings[K]) => {
      setSettings((prev) => {
        const next = { ...prev, [key]: value };
        saveRunSettings(next);
        return next;
      });
    },
    [],
  );

  const startAgent = () => void agent.run(settings);

  return (
    <div className="app-shell">
      <AgentHeader
        serverStatus={health.status}
        latencyMs={health.latencyMs}
        apiUrl={health.apiUrl}
        running={agent.running}
      />

      <div className="layout">
        <div className="main-column">
          <AgentConfigForm
            settings={settings}
            onChange={updateSetting}
            disabled={agent.running}
            running={agent.running}
            serverOnline={health.status === "online"}
            onStart={startAgent}
            onStop={agent.cancel}
            onReset={agent.reset}
            canReset={Boolean(agent.result) || agent.conversationMessages.length > 0}
            result={agent.result}
            error={agent.error}
          />
        </div>

        <div className="side-column">
          <ConnectionPanel status={health.status} onRefresh={health.check} />
          <WorkflowPipeline
            steps={agent.steps}
            running={agent.running}
            reconnected={agent.reconnected}
            taskPlanSummary={agent.result?.task_plan_summary}
          />
        </div>
      </div>
    </div>
  );
}
