/** API client for RedlineAI backend. */

import type {
  ComparisonResult,
  ComparisonSession,
  ComparisonSessionCreate,
  DocumentInfo,
  DocumentUploadResponse,
} from "@/types/api";

const BASE = import.meta.env.VITE_API_BASE_URL ?? "/api";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

// --- Documents ---

export async function uploadDocument(file: File): Promise<DocumentUploadResponse> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE}/documents/upload`, { method: "POST", body: form });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || "Upload failed");
  }
  return res.json();
}

export async function listDocuments(): Promise<DocumentInfo[]> {
  return request("/documents/");
}

export async function deleteDocument(id: string): Promise<void> {
  await request(`/documents/${id}`, { method: "DELETE" });
}

// --- Comparison ---

export async function createSession(data: ComparisonSessionCreate): Promise<ComparisonSession> {
  return request("/comparison/sessions", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function getSession(sessionId: string): Promise<ComparisonSession> {
  return request(`/comparison/sessions/${sessionId}`);
}

export async function runComparison(
  sessionId: string,
  apiKey?: string,
): Promise<{ message: string }> {
  return request(`/comparison/sessions/${sessionId}/run`, {
    method: "POST",
    headers: apiKey ? { "X-API-Key": apiKey } : {},
  });
}

export async function getResult(sessionId: string): Promise<ComparisonResult> {
  return request(`/comparison/sessions/${sessionId}/result`);
}

// --- Export ---

export async function exportRedline(
  sessionId: string,
  options: {
    include_ai_summaries?: boolean;
    include_risk_assessments?: boolean;
    include_summary_appendix?: boolean;
    show_formatting_changes?: boolean;
    version_comparison_id?: string | null;
    output_format?: string;
  } = {},
): Promise<void> {
  const res = await fetch(`${BASE}/export/sessions/${sessionId}/export`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      include_ai_summaries: options.include_ai_summaries ?? true,
      include_risk_assessments: options.include_risk_assessments ?? true,
      include_summary_appendix: options.include_summary_appendix ?? true,
      show_formatting_changes: options.show_formatting_changes ?? false,
      version_comparison_id: options.version_comparison_id ?? null,
      output_format: options.output_format ?? "docx",
    }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || "Export failed");
  }
  // Download the file
  const blob = await res.blob();
  const disposition = res.headers.get("content-disposition");
  const filenameMatch = disposition?.match(/filename="?(.+?)"?$/);
  const filename = filenameMatch?.[1] ?? "RedlineAI_export.docx";

  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
