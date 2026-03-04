"""Comparison session API routes - full pipeline wired."""

import asyncio
import logging
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException

from app.api.documents import get_document_path, _documents
from app.models.schemas import (
    AnnotatedChange,
    ComparisonMode,
    ComparisonResult,
    ComparisonSession,
    ComparisonSessionCreate,
    ReviewingParty,
    RiskSeverity,
    SessionStatus,
    VersionComparison,
)
from app.services.parser import parser_registry
from app.services.diff_engine import compare_documents, DiffChange
from app.services.ai_analyzer import analyze_changes, build_annotated_changes

logger = logging.getLogger(__name__)
router = APIRouter()

# In-memory stores for MVP
_sessions: dict[UUID, ComparisonSession] = {}
_results: dict[UUID, ComparisonResult] = {}


def _run_diff(original_path: str, modified_path: str, version_label: str) -> list[dict]:
    """Run the diff engine in a worker (serializable for ProcessPoolExecutor).

    Any PDF inputs are transparently converted to a temporary DOCX so that
    both documents go through the same DocxParser pipeline, giving the same
    paragraph granularity and heading detection as a native DOCX-to-DOCX
    comparison.
    """
    from app.services.parser import convert_pdf_to_docx

    orig_path = Path(original_path)
    mod_path = Path(modified_path)
    orig_tmp: Path | None = None
    mod_tmp: Path | None = None

    try:
        if orig_path.suffix.lower() == ".pdf":
            orig_tmp = convert_pdf_to_docx(orig_path)
            orig_path = orig_tmp
        if mod_path.suffix.lower() == ".pdf":
            mod_tmp = convert_pdf_to_docx(mod_path)
            mod_path = mod_tmp

        orig_id = uuid4()
        mod_id = uuid4()

        parser = parser_registry.get_parser(orig_path)
        orig_doc = parser.parse(orig_path, orig_id)

        parser2 = parser_registry.get_parser(mod_path)
        mod_doc = parser2.parse(mod_path, mod_id)

        changes = compare_documents(orig_doc, mod_doc, version_label)
    finally:
        if orig_tmp:
            orig_tmp.unlink(missing_ok=True)
        if mod_tmp:
            mod_tmp.unlink(missing_ok=True)

    # Serialize DiffChange to dict for cross-process transport
    return [
        {
            "change_type": c.change_type.value,
            "original_text": c.original_text,
            "modified_text": c.modified_text,
            "section_context": c.section_context,
            "is_move": c.is_move,
            "is_heading": c.is_heading,
            "similarity": c.similarity,
            "original_paragraph_id": c.original_paragraph_id,
            "modified_paragraph_id": c.modified_paragraph_id,
            "inline_diffs": [
                {"tag": d.tag, "original_span": d.original_span, "modified_span": d.modified_span}
                for d in c.inline_diffs
            ],
        }
        for c in changes
    ]


def _deserialize_diff_changes(raw: list[dict]) -> list[DiffChange]:
    """Reconstruct DiffChange objects from serialized dicts."""
    from app.models.schemas import ChangeType
    from app.services.diff_engine import DiffChange, InlineDiff

    changes = []
    for r in raw:
        changes.append(DiffChange(
            change_type=ChangeType(r["change_type"]),
            original_text=r.get("original_text"),
            modified_text=r.get("modified_text"),
            section_context=r.get("section_context"),
            is_move=r.get("is_move", False),
            is_heading=r.get("is_heading", False),
            similarity=r.get("similarity"),
            original_paragraph_id=r.get("original_paragraph_id"),
            modified_paragraph_id=r.get("modified_paragraph_id"),
            inline_diffs=[
                InlineDiff(tag=d["tag"], original_span=d["original_span"], modified_span=d["modified_span"])
                for d in r.get("inline_diffs", [])
            ],
        ))
    return changes


def _build_version_comparison(
    base_id: UUID,
    mod_id: UUID,
    version_label: str,
    reviewing_party: ReviewingParty,
) -> tuple[list[DiffChange], VersionComparison]:
    """Run diff + build annotated changes for a single pair (sync helper)."""
    base_path = get_document_path(base_id)
    mod_path = get_document_path(mod_id)

    raw_changes = _run_diff(str(base_path), str(mod_path), version_label)
    diff_changes = _deserialize_diff_changes(raw_changes)

    # AI analysis skipped in sync helper; done in _execute_comparison
    annotated = build_annotated_changes(
        diff_changes, [], reviewing_party, version_label
    )

    risk_summary: dict[RiskSeverity, int] = {}
    for ac in annotated:
        if ac.risk_assessment:
            sev = ac.risk_assessment.severity
            risk_summary[sev] = risk_summary.get(sev, 0) + 1

    vc = VersionComparison(
        original_document_id=base_id,
        modified_document_id=mod_id,
        version_label=version_label,
        changes=annotated,
        total_changes=len([a for a in annotated if a.change.is_substantive]),
        risk_summary=risk_summary,
    )
    return diff_changes, vc


async def _execute_comparison(session_id: UUID, api_key: str | None = None):
    """Execute the full comparison pipeline for a session.

    Supports three modes (ADR-006):
    - original_to_each: Each version compared against the Original
    - sequential: Each version compared against the previous version
    - cumulative: All original-to-each diffs merged into one view
    """
    session = _sessions[session_id]

    try:
        session.status = SessionStatus.COMPARING
        session.progress = 10.0

        original_id = session.original_document_id
        doc_ids = [d.id for d in session.documents if d.id != original_id]
        mode = session.comparison_mode
        version_comparisons: list[VersionComparison] = []

        total_pairs = len(doc_ids)
        if total_pairs == 0:
            raise ValueError("No modified documents to compare against.")

        if mode == ComparisonMode.ORIGINAL_TO_EACH or mode == ComparisonMode.CUMULATIVE:
            # Compare each version against the original
            for i, mod_id in enumerate(doc_ids):
                mod_info = _documents.get(mod_id)
                label = (mod_info.version_label if mod_info and mod_info.version_label else f"Version {i + 2}")

                _, vc = _build_version_comparison(
                    original_id, mod_id, label, session.reviewing_party
                )
                version_comparisons.append(vc)
                session.progress = 10 + (70 * (i + 1) / total_pairs)

            # For cumulative mode, merge all changes into a single view
            if mode == ComparisonMode.CUMULATIVE and len(version_comparisons) > 1:
                merged_changes: list[AnnotatedChange] = []
                seen_texts: set[str] = set()
                for vc in version_comparisons:
                    for ac in vc.changes:
                        # Deduplicate by original+modified text pair
                        key = f"{ac.change.original_text}|||{ac.change.modified_text}"
                        if key not in seen_texts:
                            seen_texts.add(key)
                            merged_changes.append(ac)

                risk_summary: dict[RiskSeverity, int] = {}
                for ac in merged_changes:
                    if ac.risk_assessment:
                        sev = ac.risk_assessment.severity
                        risk_summary[sev] = risk_summary.get(sev, 0) + 1

                cumulative_vc = VersionComparison(
                    original_document_id=original_id,
                    modified_document_id=doc_ids[-1],
                    version_label="Cumulative (All Versions)",
                    changes=merged_changes,
                    total_changes=len([a for a in merged_changes if a.change.is_substantive]),
                    risk_summary=risk_summary,
                )
                # Prepend cumulative as first tab, keep individual tabs after
                version_comparisons.insert(0, cumulative_vc)

        elif mode == ComparisonMode.SEQUENTIAL:
            # Compare each version against the immediately preceding one
            all_doc_ids = [original_id] + doc_ids
            for i in range(len(all_doc_ids) - 1):
                base_id = all_doc_ids[i]
                mod_id = all_doc_ids[i + 1]
                base_info = _documents.get(base_id)
                mod_info = _documents.get(mod_id)
                base_label = base_info.version_label if base_info and base_info.version_label else f"V{i + 1}"
                mod_label = mod_info.version_label if mod_info and mod_info.version_label else f"V{i + 2}"
                label = f"{base_label} → {mod_label}"

                _, vc = _build_version_comparison(
                    base_id, mod_id, label, session.reviewing_party
                )
                version_comparisons.append(vc)
                session.progress = 10 + (70 * (i + 1) / (len(all_doc_ids) - 1))

        # AI analysis pass (for all version comparisons)
        session.status = SessionStatus.ANALYZING
        session.progress = 80.0

        # Build change lists for each version comparison upfront
        all_diff_changes_for_ai = []
        for vc in version_comparisons:
            diff_changes_for_ai = []
            for ac in vc.changes:
                c = ac.change
                diff_changes_for_ai.append(DiffChange(
                    change_type=c.change_type,
                    original_text=c.original_text,
                    modified_text=c.modified_text,
                    section_context=c.section_context,
                    is_move=False,
                    is_heading=False,
                ))
            all_diff_changes_for_ai.append(diff_changes_for_ai)

        # Fan out all AI calls in parallel
        ai_results_list = await asyncio.gather(*[
            analyze_changes(diff_changes, session.reviewing_party, api_key=api_key)
            for diff_changes in all_diff_changes_for_ai
        ])

        # Merge AI results back into each version comparison
        for i, (vc, ai_results, diff_changes_for_ai) in enumerate(
            zip(version_comparisons, ai_results_list, all_diff_changes_for_ai)
        ):
            if ai_results:
                annotated = build_annotated_changes(
                    diff_changes_for_ai, ai_results,
                    session.reviewing_party, vc.version_label
                )
                for j, ac in enumerate(vc.changes):
                    if j < len(annotated) and annotated[j].ai_summary:
                        ac.ai_summary = annotated[j].ai_summary
                        ac.risk_assessment = annotated[j].risk_assessment

            session.progress = 80 + (15 * (i + 1) / len(version_comparisons))

        # Store result
        result = ComparisonResult(
            session_id=session_id,
            version_comparisons=version_comparisons,
            reviewing_party=session.reviewing_party,
            comparison_mode=session.comparison_mode,
            completed_at=datetime.utcnow(),
        )
        _results[session_id] = result

        session.status = SessionStatus.COMPLETE
        session.progress = 100.0
        logger.info(f"Comparison session {session_id} completed successfully.")

    except Exception as e:
        logger.exception(f"Comparison session {session_id} failed: {e}")
        session.status = SessionStatus.ERROR
        session.progress = 0.0


@router.post("/sessions", response_model=ComparisonSession)
async def create_session(request: ComparisonSessionCreate):
    """Create a new comparison session."""
    session_id = uuid4()

    # Validate all document IDs exist
    all_ids = [request.original_document_id] + request.document_order
    documents = []
    for i, doc_id in enumerate(all_ids):
        if doc_id not in _documents:
            raise HTTPException(status_code=404, detail=f"Document {doc_id} not found.")
        doc = _documents[doc_id].model_copy()
        if doc_id == request.original_document_id:
            doc.is_original = True
            doc.version_label = "Original"
        else:
            doc.version_label = f"Version {i + 1}"
        documents.append(doc)

    session = ComparisonSession(
        id=session_id,
        status=SessionStatus.READY,
        documents=documents,
        original_document_id=request.original_document_id,
        comparison_mode=request.comparison_mode,
        reviewing_party=request.reviewing_party,
    )

    _sessions[session_id] = session
    return session


@router.get("/sessions/{session_id}", response_model=ComparisonSession)
async def get_session(session_id: UUID):
    """Get the status of a comparison session."""
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found.")
    return _sessions[session_id]


@router.post("/sessions/{session_id}/run")
async def run_comparison(
    session_id: UUID,
    background_tasks: BackgroundTasks,
    x_api_key: str | None = Header(default=None),
):
    """Trigger the comparison pipeline for a session.

    Optionally accepts an X-API-Key header containing the user's Anthropic API
    key. When provided it is used for AI analysis in preference to the server's
    environment variable. The key is never stored — it is only held in memory
    for the duration of this background task.
    """
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found.")

    session = _sessions[session_id]

    if session.status not in (SessionStatus.READY, SessionStatus.ERROR):
        raise HTTPException(
            status_code=400,
            detail=f"Session is in '{session.status}' state and cannot be run.",
        )

    # Run comparison in background, forwarding the user-supplied key (if any)
    background_tasks.add_task(_execute_comparison, session_id, x_api_key)

    session.status = SessionStatus.COMPARING
    session.progress = 0.0

    return {"message": "Comparison started.", "session_id": str(session_id)}


@router.get("/sessions/{session_id}/result", response_model=ComparisonResult)
async def get_result(session_id: UUID):
    """Get the comparison result for a completed session."""
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found.")

    session = _sessions[session_id]
    if session.status != SessionStatus.COMPLETE:
        raise HTTPException(
            status_code=400,
            detail=f"Session is not complete. Current status: {session.status}",
        )

    if session_id not in _results:
        raise HTTPException(status_code=404, detail="Result not found.")

    return _results[session_id]
