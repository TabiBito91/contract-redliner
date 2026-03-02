/** TypeScript types matching backend Pydantic schemas. */

export type ChangeType = "addition" | "deletion" | "modification" | "move" | "format_only";
export type RiskSeverity = "critical" | "high" | "medium" | "low" | "info";
export type ReviewingParty = "original_drafter" | "counterparty" | "neutral";
export type ComparisonMode = "original_to_each" | "sequential" | "cumulative";
export type SessionStatus = "uploading" | "ready" | "comparing" | "analyzing" | "complete" | "error";

export interface DocumentInfo {
  id: string;
  filename: string;
  file_size: number;
  upload_time: string;
  page_count: number | null;
  version_label: string | null;
  is_original: boolean;
}

export interface DocumentUploadResponse {
  document: DocumentInfo;
  message: string;
}

export interface ComparisonSessionCreate {
  original_document_id: string;
  document_order: string[];
  comparison_mode: ComparisonMode;
  reviewing_party: ReviewingParty;
}

export interface ComparisonSession {
  id: string;
  status: SessionStatus;
  documents: DocumentInfo[];
  original_document_id: string | null;
  comparison_mode: ComparisonMode;
  reviewing_party: ReviewingParty;
  created_at: string;
  progress: number;
}

export interface Change {
  id: string;
  change_type: ChangeType;
  original_text: string | null;
  modified_text: string | null;
  section_context: string | null;
  original_paragraph_id: string | null;
  modified_paragraph_id: string | null;
  is_substantive: boolean;
  version_source: string | null;
}

export interface AISummary {
  change_id: string;
  summary: string;
  change_category: string;
  is_substantive: boolean;
  related_changes: string[];
}

export interface RiskAssessment {
  change_id: string;
  severity: RiskSeverity;
  summary: string;
  risk_explanation: string;
  recommendation: string;
  confidence: number;
  reviewing_party: ReviewingParty;
}

export interface AnnotatedChange {
  change: Change;
  ai_summary: AISummary | null;
  risk_assessment: RiskAssessment | null;
}

export interface VersionComparison {
  original_document_id: string;
  modified_document_id: string;
  version_label: string;
  changes: AnnotatedChange[];
  total_changes: number;
  risk_summary: Record<string, number>;
}

export interface ComparisonResult {
  session_id: string;
  version_comparisons: VersionComparison[];
  reviewing_party: ReviewingParty;
  comparison_mode: ComparisonMode;
  completed_at: string;
}
