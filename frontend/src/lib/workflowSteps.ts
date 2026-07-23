import type { StepState, WorkflowStep } from "../types";

export const WORKFLOW_STEPS: WorkflowStep[] = [
  {
    id: "prepare_input",
    nodes: ["prepare_input"],
    label: "📥 Input Preparation",
    description: "Format the user input and message history",
    emoji: "📥",
  },
  {
    id: "decision_agent",
    nodes: ["decision_agent"],
    label: "🧠 Decision Routing",
    description: "Analyze query and choose execution path",
    emoji: "🧠",
  },
  {
    id: "call_model",
    nodes: ["call_model"],
    label: "🤖 General LLM",
    description: "Process conversational query or determine tool usage",
    optional: true,
    emoji: "🤖",
  },
  {
    id: "tools",
    nodes: ["tools"],
    label: "🔧 Tool Execution",
    description: "Execute tools chosen by the LLM (store SQL, PDF, math, etc.)",
    optional: true,
    emoji: "🔧",
  },
  {
    id: "run_calculator",
    nodes: ["run_calculator"],
    label: "🧮 Calculator",
    description: "Direct Casio-style math expression solver",
    optional: true,
    emoji: "🧮",
  },
  {
    id: "run_web_search",
    nodes: ["run_web_search"],
    label: "🌐 Web Search",
    description: "Perform DuckDuckGo search for live information",
    optional: true,
    emoji: "🌐",
  },
  {
    id: "run_file_search",
    nodes: ["run_file_search"],
    label: "🗂️ File Search",
    description: "Search local files and directories",
    optional: true,
    emoji: "🗂️",
  },
  {
    id: "run_location",
    nodes: ["run_location"],
    label: "📍 Live Location",
    description: "Reverse geocode coordinates and search nearby places",
    optional: true,
    emoji: "📍",
  },
  {
    id: "run_pdf_analysis",
    nodes: ["run_pdf_analysis"],
    label: "📄 PDF Analysis",
    description: "Retrieve uploaded PDF chunks with BGE semantic search, then answer",
    optional: true,
    emoji: "📄",
  },
  {
    id: "run_business_rag",
    nodes: ["run_business_rag"],
    label: "📚 Business RAG",
    description:
      "Hybrid retrieve top 5 → trust-layer reads each → answer + list all 5 Sources",
    optional: true,
    emoji: "📚",
  },
  {
    id: "reject_db_mutation",
    nodes: ["reject_db_mutation"],
    label: "🛡️ Read-Only Guard",
    description: "Rules + AI intent: block real DB writes, allow legit read/advice asks",
    optional: true,
    emoji: "🛡️",
  },
  {
    id: "run_store_database",
    nodes: ["run_store_database"],
    label: "🗄️ Store Database",
    description: "Prepare query_store_database tool call from LLM SQL",
    optional: true,
    emoji: "🗄️",
  },
  {
    id: "run_gmail_inbox",
    nodes: ["run_gmail_inbox"],
    label: "📬 Gmail Inbox",
    description: "Read unread Gmail, summarize threads, prepare replies",
    optional: true,
    emoji: "📬",
  },
  {
    id: "run_email",
    nodes: ["run_email"],
    label: "📧 Email Dispatch",
    description: "Send results or PDFs via Gmail SMTP",
    optional: true,
    emoji: "📧",
  },
  {
    id: "math_and_email",
    nodes: ["math_and_email"],
    label: "🧮 + 📧 Math & Email",
    description: "Calculate expression and email result in one pass",
    optional: true,
    emoji: "🚀",
  },
  {
    id: "execute_workflow",
    nodes: ["execute_workflow"],
    label: "⚡ Multi-Step Pipeline",
    description: "Batch process intro, math, PDF, and email sequentially",
    optional: true,
    emoji: "⚡",
  },
];

const NODE_TO_STEP = new Map<string, string>();
for (const step of WORKFLOW_STEPS) {
  for (const node of step.nodes) {
    NODE_TO_STEP.set(node, step.id);
  }
}

export function stepIdForNode(nodeName: string): string | undefined {
  return NODE_TO_STEP.get(nodeName);
}

export function initialStepStates(): StepState[] {
  return WORKFLOW_STEPS.map((step) => ({
    id: step.id,
    status: "pending" as const,
  }));
}

export function detailForNode(nodeName: string, payload: Record<string, unknown>): string {
  switch (nodeName) {
    case "prepare_input":
      return "Input structured and appended to history.";
    case "decision_agent":
      return payload.task_plan_summary ? String(payload.task_plan_summary) : "Routing decision made.";
    case "call_model":
      return "LLM processing complete.";
    case "tools":
      return "Selected tool executed successfully.";
    case "run_calculator":
      return "Math expression evaluated.";
    case "run_web_search":
      return "Web search completed.";
    case "run_file_search":
      return "File search completed.";
    case "run_location":
      return "Location lookup completed.";
    case "run_pdf_analysis":
      return "PDF chunks retrieved with BGE and answered from the document.";
    case "run_business_rag":
      return "Top 5 retrieved, each source judged, answer grounded with all Sources listed.";
    case "reject_db_mutation":
      return (
        (typeof payload.db_guard_detail === "string" && payload.db_guard_detail) ||
        "Blocked write request — rules + AI read-only guard."
      );
    case "run_store_database":
      return "Store database query completed.";
    case "run_gmail_inbox":
      return "Gmail inbox read / reply flow completed.";
    case "run_email":
      return "Email sent successfully.";
    case "math_and_email":
      return "Calculated and emailed results.";
    case "execute_workflow":
      return "Multi-step workflow executed.";
    default:
      return "Done";
  }
}
