import type { AgentState } from "../types";

export interface GeneratedPdfInfo {
  filename: string;
  downloadUrl: string;
  sourcePath?: string;
}

function messageText(content: unknown): string {
  if (typeof content === "string") return content;
  if (Array.isArray(content)) {
    return content
      .map((part) => {
        if (typeof part === "string") return part;
        if (part && typeof part === "object" && "text" in part) {
          return String((part as { text?: string }).text ?? "");
        }
        return "";
      })
      .join("\n");
  }
  return content != null ? String(content) : "";
}

/** Pull a PDF path from agent text (Verified path / tool success lines). */
export function extractPdfPathFromText(text: string): string | null {
  if (!text) return null;

  const patterns = [
    /Verified PDF path:\s*`([^`]+)`/i,
    /Verified PDF path:\s*(\S+\.pdf)/i,
    /PDF report successfully generated:\s*(\S+\.pdf)/i,
    /Table PDF report successfully generated:\s*(\S+\.pdf)/i,
    /Attached file:\s*[^(]*\(([^)]+\.pdf)\)/i,
    /(\/(?:[\w.-]+\/)+[\w.-]+\.pdf)/i,
    /(\.\/reports\/[\w.-]+\.pdf)/i,
  ];

  for (const pattern of patterns) {
    const match = text.match(pattern);
    if (match?.[1]) return match[1].trim();
  }
  return null;
}

export function generatedPdfFromResult(result: AgentState | null): GeneratedPdfInfo | null {
  if (!result) return null;

  let filename = result.generated_pdf_filename?.trim() || "";
  let sourcePath = result.generated_pdf_path?.trim() || "";

  if (!filename || !sourcePath) {
    const blobs: string[] = [];
    if (result.task_plan_summary) blobs.push(result.task_plan_summary);
    for (const msg of result.messages ?? []) {
      blobs.push(messageText(msg.content));
    }
    const found = extractPdfPathFromText(blobs.join("\n"));
    if (found) {
      sourcePath = sourcePath || found;
      filename = filename || found.split(/[\\/]/).pop() || "";
    }
  }

  if (!filename.toLowerCase().endsWith(".pdf")) return null;
  // Prevent path traversal in the download URL
  const safeName = filename.replace(/^.*[\\/]/, "");
  if (!safeName.toLowerCase().endsWith(".pdf")) return null;

  return {
    filename: safeName,
    downloadUrl: `/generated-reports/${encodeURIComponent(safeName)}`,
    sourcePath: sourcePath || undefined,
  };
}
