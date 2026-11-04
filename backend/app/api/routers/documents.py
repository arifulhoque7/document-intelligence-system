import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import current_user
from app.api.serializers import document_out
from app.core.config import get_settings
from app.core.db import get_db
from app.models import Document, DocumentPage, ProcessingEvent, User
from app.processing.detect import detect_type
from app.services.storage import UploadTooLarge, safe_display_name, save_upload
from app.worker import enqueue

router = APIRouter(prefix="/api/documents", tags=["documents"])
# A queued/processing job with no progress for this long is treated as lost (e.g. worker killed before acking).
STALE_AFTER = timedelta(minutes=10)
MEDIA = {"pdf": "application/pdf", "image": "image/*", "tiff": "image/tiff", "csv": "text/csv",
         "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xls": "application/vnd.ms-excel"}


def _stale(doc: Document) -> bool:
    return doc.status in ("queued", "processing") and doc.updated_at < datetime.now(UTC) - STALE_AFTER


def _get(db: Session, doc_id: uuid.UUID) -> Document:
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    return doc


@router.post("", status_code=202)
async def upload(files: list[UploadFile] = File(...), user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Accept many files; each is type-checked by content and queued. Bad files are rejected individually."""
    cfg = get_settings()
    if len(files) > cfg.max_files_per_upload:
        raise HTTPException(413, f"At most {cfg.max_files_per_upload} files per upload")
    accepted, rejected = [], []
    for f in files:
        name = safe_display_name(f.filename)
        try:
            path, size, sha = await save_upload(f)
        except UploadTooLarge as e:
            rejected.append({"filename": name, "reason": str(e)})
            continue
        if size == 0:
            path.unlink(missing_ok=True)
            rejected.append({"filename": name, "reason": "File is empty"})
            continue
        file_type = detect_type(path)
        if file_type == "unknown":
            # Keep it as a failed document so the user sees why (e.g. a corrupted file renamed .pdf).
            doc = Document(filename=name, file_type="unknown", size_bytes=size, sha256=sha, storage_path=str(path),
                           status="failed", error="Unsupported or unrecognised file content", uploaded_by=user.id)
            db.add(doc)
            db.commit()
            rejected.append({"filename": name, "reason": doc.error, "id": str(doc.id)})
            continue
        dup = db.scalar(select(Document.id).where(Document.sha256 == sha).limit(1))
        doc = Document(filename=name, file_type=file_type, size_bytes=size, sha256=sha, storage_path=str(path), uploaded_by=user.id)
        doc.events.append(ProcessingEvent(stage="queued", status="ok", message=f"Detected type: {file_type}"))
        db.add(doc)
        db.commit()
        enqueue(doc.id)
        accepted.append({"id": str(doc.id), "filename": name, "file_type": file_type, "duplicate_of": str(dup) if dup else None})
    return {"accepted": accepted, "rejected": rejected}


@router.get("")
def list_documents(
    status: str | None = None,
    file_type: str | None = None,
    q: str | None = Query(None, description="Filename or full-text match on document text"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    _: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    stmt = select(Document)
    if status:
        stmt = stmt.where(Document.status == status)
    if file_type:
        stmt = stmt.where(Document.file_type == file_type)
    if q:
        text_match = select(DocumentPage.document_id).where(DocumentPage.tsv.op("@@")(func.websearch_to_tsquery("simple", q)))
        stmt = stmt.where(or_(Document.filename.ilike(f"%{q}%"), Document.id.in_(text_match)))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    docs = db.scalars(
        stmt.options(selectinload(Document.invoices)).order_by(Document.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return {"total": total, "page": page, "items": [document_out(d) for d in docs]}


@router.get("/{doc_id}")
def get_document(doc_id: uuid.UUID, _: User = Depends(current_user), db: Session = Depends(get_db)):
    return document_out(_get(db, doc_id), detail=True)


@router.get("/{doc_id}/text")
def get_text(doc_id: uuid.UUID, _: User = Depends(current_user), db: Session = Depends(get_db)):
    doc = _get(db, doc_id)
    return [{"page_no": p.page_no, "sheet_name": p.sheet_name, "method": p.method, "ocr_confidence": p.ocr_confidence, "text": p.text} for p in doc.pages]


@router.get("/{doc_id}/file")
def get_file(doc_id: uuid.UUID, _: User = Depends(current_user), db: Session = Depends(get_db)):
    doc = _get(db, doc_id)
    # Served as a download, never inline, so an uploaded file cannot run script in our origin.
    return FileResponse(doc.storage_path, media_type=MEDIA.get(doc.file_type, "application/octet-stream"),
                        filename=doc.filename, content_disposition_type="attachment")


@router.post("/{doc_id}/reprocess", status_code=202)
def reprocess(doc_id: uuid.UUID, _: User = Depends(current_user), db: Session = Depends(get_db)):
    doc = _get(db, doc_id)
    if doc.file_type == "unknown":
        raise HTTPException(422, "File type is not supported; upload a valid file instead")
    if doc.status in ("queued", "processing") and not _stale(doc):
        raise HTTPException(409, "Document is already being processed")
    doc.status, doc.progress, doc.error = "queued", 0, None
    doc.events.append(ProcessingEvent(stage="queued", status="ok", message="Reprocess requested"))
    db.commit()
    enqueue(doc.id)
    return {"id": str(doc.id), "status": doc.status}


@router.post("/reprocess-failed", status_code=202)
def reprocess_failed(_: User = Depends(current_user), db: Session = Depends(get_db)):
    candidates = db.scalars(
        select(Document).where(Document.status.in_(("failed", "queued", "processing")), Document.file_type != "unknown")
    ).all()
    docs = [d for d in candidates if d.status == "failed" or _stale(d)]
    for doc in docs:
        doc.status, doc.progress, doc.error = "queued", 0, None
        doc.events.append(ProcessingEvent(stage="queued", status="ok", message="Bulk reprocess of failed or stuck jobs"))
    db.commit()
    for doc in docs:
        enqueue(doc.id)
    return {"requeued": [str(d.id) for d in docs]}
