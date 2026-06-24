import { useCallback, useState } from "react";
import { runAgentChat } from "../lib/agentClient";
import { initialStepStates } from "../lib/workflowSteps";
import type { AgentState, LogEntry, RunRequest, StepState } from "../types";

export function useAgentRun() {
  const [running, setRunning] = useState(false);
  const [reconnected, setReconnected] = useState(false);
  const [steps, setSteps] = useState<StepState[]>(initialStepStates());
  const [result, setResult] = useState<AgentState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [runId, setRunId] = useState<string | null>(null);

  const pushLog = useCallback((level: LogEntry["level"], message: string) => {
    setLogs((prev) => [
      ...prev,
      {
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        time: new Date().toLocaleTimeString(),
        level,
        message,
      },
    ]);
  }, []);

  const run = useCallback(async (request: RunRequest) => {
    if (!request.user_input?.trim()) {
      setError("User input is required.");
      return;
    }

    setRunning(true);
    setError(null);
    setResult(null);
    setLogs([]);
    setReconnected(false);
    setThreadId(null);
    setRunId(null);

    // Mark first step as running
    setSteps((prev) =>
      prev.map((s, i) => i === 0 ? { ...s, status: "running" } : { ...s, status: "pending" })
    );

    pushLog("info", "🚀 Sending request to Andromeda agent...");

    try {
      const { threadId: tid, response } = await runAgentChat(
        request,
        (eventType, data) => {
          // Live progress from SSE stream
          if (eventType === "updates" && data && typeof data === "object") {
            const upd = data as Record<string, unknown>;
            const nodeName = Object.keys(upd)[0];
            if (nodeName) {
              pushLog("info", `⚙️ Node active: ${nodeName}`);
            }
          }
        },
      );

      setThreadId(tid);

      // Update result state with the text returned
      setResult({ task_plan_summary: response } as AgentState);

      // Mark all steps completed
      setSteps((prev) =>
        prev.map((s) => ({ ...s, status: "completed", detail: "Done" }))
      );

      pushLog("success", "✅ Agent request completed successfully!");
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(message);
      pushLog("error", `❌ Error: ${message}`);

      setSteps((prev) =>
        prev.map((s) => s.status === "running" ? { ...s, status: "error", detail: message } : s)
      );
    } finally {
      setRunning(false);
    }
  }, [pushLog]);

  const cancel = useCallback(() => {
    if (running) {
      setRunning(false);
      pushLog("warn", "⏹️ Agent run stopped (UI only)");
    }
  }, [running, pushLog]);

  const reset = useCallback(() => {
    setRunning(false);
    setReconnected(false);
    setSteps(initialStepStates());
    setResult(null);
    setError(null);
    setLogs([]);
    setThreadId(null);
    setRunId(null);
  }, []);

  return {
    running,
    reconnected,
    steps,
    result,
    error,
    logs,
    threadId,
    runId,
    run,
    cancel,
    reset,
  };
}
