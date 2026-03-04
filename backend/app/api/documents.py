"""Document upload and management API routes."""

import asyncio
import shutil
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, UploadFile, File

from app.core.config import settings
from app.models.schemas import DocumentInfo, DocumentUploadResponse

router = APIRouter()

# In-memory store for MVP (will be replaced with DB)
_documents: dict[UUID, DocumentInfo] = {}
_document_paths: dict[UUID, Path] = {}


def _validate_file(file: UploadFile) -> None:
    """Validate uploaded file is an allowed DOCX."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")

    ext = Path(file.filename).suffix.lower()
    if ext not in settings.allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {settings.allowed_extensions}",
        )

    if file.size and file.size > settings.max_file_size_mb * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail=f"File exceeds maximum size of {settings.max_file_size_mb}MB.",
        )


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(file: UploadFile = File(...)):
    """Upload a DOCX document for comparison."""
    _validate_file(file)

    doc_id = uuid4()
    suffix = Path(file.filename).suffix.lower()
    upload_path = settings.upload_dir / f"{doc_id}{suffix}"

    # Save file to disk
    with open(upload_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Convert PDF to DOCX once so every downstream consumer (comparison +
    # export) works from the same file and paragraph texts always match.
    # Run in a thread so the async event loop stays responsive during conversion.
    # Use shutil.move instead of Path.rename for cross-filesystem safety on Windows.
    if suffix == ".pdf":
        from app.services.parser import convert_pdf_to_docx
        docx_path = settings.upload_dir / f"{doc_id}.docx"

        def _convert():
            tmp = convert_pdf_to_docx(upload_path)
            shutil.move(str(tmp), str(docx_path))

        await asyncio.to_thread(_convert)
        upload_path.unlink(missing_ok=True)  # original PDF no longer needed
        upload_path = docx_path

    file_size = upload_path.stat().st_size

    doc_info = DocumentInfo(
        id=doc_id,
        filename=file.filename,
        file_size=file_size,
    )

    _documents[doc_id] = doc_info
    _document_paths[doc_id] = upload_path

    return DocumentUploadResponse(
        document=doc_info,
        message=f"Document '{file.filename}' uploaded successfully.",
    )


@router.get("/", response_model=list[DocumentInfo])
async def list_documents():
    """List all uploaded documents."""
    return list(_documents.values())


@router.get("/{document_id}", response_model=DocumentInfo)
async def get_document(document_id: UUID):
    """Get info for a specific document."""
    if document_id not in _documents:
        raise HTTPException(status_code=404, detail="Document not found.")
    return _documents[document_id]


@router.delete("/{document_id}")
async def delete_document(document_id: UUID):
    """Delete an uploaded document."""
    if document_id not in _documents:
        raise HTTPException(status_code=404, detail="Document not found.")

    # Remove file from disk
    path = _document_paths.get(document_id)
    if path and path.exists():
        path.unlink()

    del _documents[document_id]
    _document_paths.pop(document_id, None)

    return {"message": "Document deleted."}


def get_document_path(document_id: UUID) -> Path:
    """Get the filesystem path for a document (used by other services)."""
    if document_id not in _document_paths:
        raise HTTPException(status_code=404, detail="Document not found.")
    return _document_paths[document_id]
