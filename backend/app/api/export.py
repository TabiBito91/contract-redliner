"""Export API routes for generating output documents."""

from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.api.comparison import _sessions, _results
from app.api.documents import get_document_path
from app.core.config import settings
from app.models.schemas import ExportOptions, SessionStatus
from app.services.output_generator import generate_redline_docx

router = APIRouter()


@router.post("/sessions/{session_id}/export")
async def export_comparison(session_id: UUID, options: ExportOptions):
    """Generate and download a formatted comparison output document."""
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found.")

    session = _sessions[session_id]
    if session.status != SessionStatus.COMPLETE:
        raise HTTPException(
            status_code=400,
            detail=f"Session not complete. Current status: {session.status}",
        )

    if session_id not in _results:
        raise HTTPException(status_code=404, detail="Result not found.")

    result = _results[session_id]

    # Determine which version comparison to export
    if options.version_comparison_id:
        # Find the specific version comparison by modified_document_id
        vc = None
        for v in result.version_comparisons:
            if v.modified_document_id == options.version_comparison_id:
                vc = v
                break
        if vc is None:
            raise HTTPException(status_code=404, detail="Version comparison not found.")
    else:
        # Default to first version comparison
        if not result.version_comparisons:
            raise HTTPException(status_code=400, detail="No comparisons available.")
        vc = result.version_comparisons[0]

    # Get original document path
    original_path = get_document_path(session.original_document_id)

    # Generate output file
    output_dir = settings.upload_dir / "exports"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_filename = f"redline_{session_id}_{uuid4().hex[:8]}.docx"
    output_path = output_dir / output_filename

    generate_redline_docx(
        original_path=original_path,
        annotated_changes=vc.changes,
        options=options,
        output_path=output_path,
    )

    # Determine a user-friendly download filename
    download_name = f"RedlineAI_{vc.version_label.replace(' ', '_')}.docx"

    return FileResponse(
        path=str(output_path),
        filename=download_name,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
