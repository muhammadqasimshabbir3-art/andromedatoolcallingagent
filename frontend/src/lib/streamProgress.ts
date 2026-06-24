import type { AgentState, StepState, StepStatus } from "../types";
import { detailForNode, initialStepStates, stepIdForNode, WORKFLOW_STEPS } from "./workflowSteps";

export interface ThreadSnapshot {
  values?: AgentState | Record<string, unknown>;
  next?: string[];
  tasks?: Array<{ name: string; result?: unknown; error?: string | null }>;
}

export function normalizeStreamEvent(raw: string): string {
  return raw.split("|")[0]?.trim() ?? raw;
}

export function normalizeNodeName(raw: string): string {
  const base = raw.split("|")[0]?.trim() ?? raw;
  return base.replace(/^graph:/, "");
}

export function parseEventNodeName(data: unknown): string | null {
  if (!data || typeof data !== "object") return null;
  const evt = data as Record<string, unknown>;
  const metadata = evt.metadata as Record<string, unknown> | undefined;
  const fromMeta = metadata?.langgraph_node;
  if (typeof fromMeta === "string" && fromMeta) return fromMeta;
  if (typeof evt.name === "string" && evt.name) return evt.name;
  return null;
}

export function parseEventNodeOutput(data: unknown): Record<string, unknown> {
  if (!data || typeof data !== "object") return {};
  const evt = data as Record<string, unknown>;
  const payload = evt.data;
  if (!payload || typeof payload !== "object") return {};
  const record = payload as Record<string, unknown>;
  const output = record.output;
  if (output && typeof output === "object" && !Array.isArray(output)) {
    return output as Record<string, unknown>;
  }
  return record;
}

export function isChainStartEvent(data: unknown): boolean {
  if (!data || typeof data !== "object") return false;
  const evt = data as Record<string, unknown>;
  return evt.event === "on_chain_start" || evt.event === "on_tool_start";
}

export function isChainEndEvent(data: unknown): boolean {
  if (!data || typeof data !== "object") return false;
  const evt = data as Record<string, unknown>;
  return evt.event === "on_chain_end" || evt.event === "on_tool_end";
}

function activeGraphNodes(thread: ThreadSnapshot): string[] {
  const fromTasks = (thread.tasks ?? [])
    .filter((task) => !task.error && task.result === undefined)
    .map((task) => normalizeNodeName(task.name));
  if (fromTasks.length) return fromTasks;
  return (thread.next ?? []).map((raw) => normalizeNodeName(raw));
}

export function markStepRunning(steps: StepState[], stepId: string, detail?: string): StepState[] {
  return steps.map((step) => {
    if (step.id === stepId) {
      return {
        ...step,
        status: "running" as StepStatus,
        detail: detail ?? step.detail,
        startedAt: step.startedAt ?? new Date().toISOString(),
      };
    }
    if (step.status === "running") {
      return { ...step, status: "pending" as StepStatus, detail: undefined };
    }
    return step;
  });
}

export function markStepCompleted(steps: StepState[], stepId: string, detail?: string): StepState[] {
  return steps.map((step) => {
    if (step.id === stepId) {
      return {
        ...step,
        status: "completed" as StepStatus,
        detail: detail ?? step.detail,
        completedAt: new Date().toISOString(),
      };
    }
    return step;
  });
}

export function startPipeline(steps: StepState[]): StepState[] {
  if (!WORKFLOW_STEPS.length) return steps;
  return markStepRunning(steps, WORKFLOW_STEPS[0].id, "Agent starting…");
}

export function buildPipelineFromState(
  state: AgentState,
  nextNodes: string[] = [],
  thread: ThreadSnapshot = {},
): { steps: StepState[]; completedNodes: Set<string> } {
  const completedNodes = new Set<string>();
  let steps = initialStepStates();

  const activeNodes = activeGraphNodes({ ...thread, next: nextNodes });
  
  // For Andromeda, we just look at the active nodes and completed nodes 
  // passed through events. Since we cannot easily infer from state alone which
  // node is complete (except maybe decision_agent), we rely more on the streaming
  // updates. Here we do a simple mapping.
  
  if (state.task_plan_summary || state.agent_route) {
    completedNodes.add("prepare_input");
    completedNodes.add("decision_agent");
    steps = markStepCompleted(steps, "prepare_input", detailForNode("prepare_input", state as any));
    steps = markStepCompleted(steps, "decision_agent", detailForNode("decision_agent", state as any));
  }

  if (activeNodes.length > 0) {
    const activeNode = activeNodes[0];
    const stepId = stepIdForNode(activeNode);
    if (stepId) {
      steps = markStepRunning(steps, stepId, detailForNode(activeNode, state as any));
    }
  }

  // If there are no next nodes and we have messages, we can assume the workflow has finished.
  if (nextNodes.length === 0 && state.messages && state.messages.length > 0) {
     steps = steps.map(s => {
       if (s.status === "running") {
         return { ...s, status: "completed" as StepStatus, completedAt: new Date().toISOString() };
       }
       return s;
     });
  }

  return { steps, completedNodes };
}

export function finalizePipeline(
  _steps: StepState[],
  state: AgentState,
  completedNodes: Set<string>,
  nextNodes?: string[],
  thread?: ThreadSnapshot,
): StepState[] {
  const rebuilt = buildPipelineFromState(state, nextNodes ?? [], thread ?? {});
  completedNodes.clear();
  for (const node of rebuilt.completedNodes) {
    completedNodes.add(node);
  }
  return rebuilt.steps;
}

export function payloadForNode(
  _nodeName: string,
  nodeUpdate: Record<string, unknown>,
  state: AgentState,
): Record<string, unknown> {
  return { ...state, ...nodeUpdate };
}

export function progressPercent(steps: StepState[]): number {
  const total = WORKFLOW_STEPS.length;
  if (!total) return 0;
  const completed = steps.filter((s) => s.status === "completed" || s.status === "skipped").length;
  const running = steps.some((s) => s.status === "running") ? 0.5 : 0;
  return Math.min(100, Math.round(((completed + running) / total) * 100));
}
