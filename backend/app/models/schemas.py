"""Pydantic models for API request/response schemas."""

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


# --- Enums ---

class ChangeType(str, Enum):
    ADDITION = "addition"
    DELETION = "deletion"
    MODIFICATION = "modification"
    MOVE = "move"
    FORMAT_ONLY = "format_only"


class RiskSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ReviewingParty(str, Enum):
    ORIGINAL_DRAFTER = "original_drafter"
    COUNTERPARTY = "counterparty"
    NEUTRAL = "neutral"


class ComparisonMode(str, Enum):
    ORIGINAL_TO_EACH = "original_to_each"
    SEQUENTIAL = "sequential"
    CUMULATIVE = "cumulative"


class SessionStatus(str, Enum):
    UPLOADING = "uploading"
    READY = "ready"
    COMPARING = "comparing"
    ANALYZING = "analyzing"
    COMPLETE = "complete"
    ERROR = "error"


# --- Document Models ---

class DocumentInfo(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    filename: str
    file_size: int
    upload_time: datetime = Field(default_factory=datetime.utcnow)
    page_count: int | None = None
    version_label: str | None = None  # e.g., "Original", "Version 2"
    is_original: bool = False


class DocumentUploadResponse(BaseModel):
    document: DocumentInfo
    message: str


# --- Comparison Session Models ---

class ComparisonSessionCreate(BaseModel):
    original_document_id: UUID
    document_order: list[UUID]  # ordered list of version document IDs
    comparison_mode: ComparisonMode = ComparisonMode.ORIGINAL_TO_EACH
    reviewing_party: ReviewingParty = ReviewingParty.NEUTRAL


class ComparisonSession(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    status: SessionStatus = SessionStatus.UPLOADING
    documents: list[DocumentInfo] = []
    original_document_id: UUID | None = None
    comparison_mode: ComparisonMode = ComparisonMode.ORIGINAL_TO_EACH
    reviewing_party: ReviewingParty = ReviewingParty.NEUTRAL
    created_at: datetime = Field(default_factory=datetime.utcnow)
    progress: float = 0.0  # 0-100


# --- Parsed Document Structure ---

class DocumentParagraph(BaseModel):
    """A single paragraph/provision from a parsed document."""
    id: str  # unique identifier within the document
    text: str
    heading_level: int | None = None  # None = normal paragraph, 1-9 = heading
    section_number: str | None = None  # e.g., "8.2"
    list_level: int | None = None
    list_marker: str | None = None
    style_name: str | None = None
    parent_section: str | None = None  # section_number of parent heading


class DocumentTable(BaseModel):
    """A table from a parsed document."""
    id: str
    rows: list[list[str]]  # rows x cols of cell text
    section_context: str | None = None  # which section the table is in


class ParsedDocument(BaseModel):
    """Intermediate representation of a parsed document."""
    document_id: UUID
    paragraphs: list[DocumentParagraph] = []
    tables: list[DocumentTable] = []
    headers: list[DocumentParagraph] = []
    footers: list[DocumentParagraph] = []
    footnotes: list[DocumentParagraph] = []


# --- Diff / Change Models ---

class Change(BaseModel):
    """A single detected change between two document versions."""
    id: UUID = Field(default_factory=uuid4)
    change_type: ChangeType
    original_text: str | None = None
    modified_text: str | None = None
    section_context: str | None = None  # e.g., "Section 8.2 - Limitation of Liability"
    original_paragraph_id: str | None = None
    modified_paragraph_id: str | None = None
    is_substantive: bool = True
    version_source: str | None = None  # which version introduced this change


class AISummary(BaseModel):
    """AI-generated summary for a change."""
    change_id: UUID
    summary: str  # plain-English description
    change_category: str  # e.g., "scope narrowing", "liability shift"
    is_substantive: bool
    related_changes: list[UUID] = []  # IDs of related/cascading changes


class RiskAssessment(BaseModel):
    """AI-generated risk assessment for a change."""
    change_id: UUID
    severity: RiskSeverity
    summary: str
    risk_explanation: str
    recommendation: str
    confidence: int = Field(ge=0, le=100)
    reviewing_party: ReviewingParty


class AnnotatedChange(BaseModel):
    """A change with its AI summary and risk assessment attached."""
    change: Change
    ai_summary: AISummary | None = None
    risk_assessment: RiskAssessment | None = None


# --- Comparison Result ---

class VersionComparison(BaseModel):
    """Result of comparing one version against the original."""
    original_document_id: UUID
    modified_document_id: UUID
    version_label: str
    changes: list[AnnotatedChange] = []
    total_changes: int = 0
    risk_summary: dict[RiskSeverity, int] = {}  # count by severity


class ComparisonResult(BaseModel):
    """Full comparison result for a session."""
    session_id: UUID
    version_comparisons: list[VersionComparison] = []
    reviewing_party: ReviewingParty
    comparison_mode: ComparisonMode
    completed_at: datetime = Field(default_factory=datetime.utcnow)


# --- Export Options ---

class ExportOptions(BaseModel):
    include_ai_summaries: bool = True
    include_risk_assessments: bool = True
    include_summary_appendix: bool = True
    show_formatting_changes: bool = False
    version_comparison_id: UUID | None = None  # specific version, or None for all
    output_format: str = "docx"  # "docx" or "pdf"
