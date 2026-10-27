from __future__ import annotations

import hashlib
import logging
import os
import uuid
from math import ceil
from pathlib import Path
from typing import Any

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.core.config import UPLOAD_DIR
from app.database import SessionLocal, get_db
from app.schemas.documents import ShareDocumentRequest, SharePermissionUpdate, VisibilityUpdate
from app.services.document_access import can_edit_document, can_view_document, is_admin
from app.services.security import get_current_user, get_optional_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["documents"])

MAX_PDF_BYTES = 50 * 1024 * 1024
VALID_VISIBILITY = {"private", "shared", "public"}


def _can_view_document(document: models.Document, user: models.User | None) -> bool:
    return can_view_document(document, user)


def _serialize_document(
    document: models.Document,
    db: Session,
    user: models.User | None = None,
    owner: models.User | None = None,
) -> dict[str, Any]:
    """Serialize only fields that exist in the Studelytics SQL schema.

    Empty `tags` and a null `category` are compatibility-only values for the
    old React Dashboard. They are not stored in PostgreSQL because the current
    schema has no tags/categories tables or document columns for them.
    """
    if owner is None:
        owner = db.query(models.User).filter(models.User.id == document.owner_id).first()

    is_owner = bool(user and document.owner_id == user.id)
    can_edit = can_edit_document(document, user)
    can_view = _can_view_document(document, user)

    upload_date = document.upload_date.isoformat() if document.upload_date else None
    return {
        "id": document.id,
        "owner_id": document.owner_id,
        "owner_username": owner.username if owner else "Ẩn danh",
        "owner_email": owner.email if owner else None,
        "title": document.title,
        "description": document.description or "",
        "total_pages": document.total_pages,
        "status": document.status,
        "visibility": document.visibility,
        "upload_date": upload_date,
        "created_at": upload_date,
        "is_owner": is_owner,
        "can_edit": can_edit,
        "can_view": can_view,
        # Frontend compatibility: these are not persisted in the new schema.
        "category": None,
        "tags": [],
        "views": 0,
    }


def _serialize_documents(
    documents: list[models.Document], db: Session, user: models.User | None
) -> list[dict[str, Any]]:
    """Serialize a page with a single owner lookup to avoid N+1 queries."""
    if not documents:
        return []
    owner_ids = {doc.owner_id for doc in documents}
    owners = {
        owner.id: owner
        for owner in db.query(models.User).filter(models.User.id.in_(owner_ids)).all()
    }
    return [
        _serialize_document(doc, db, user, owner=owners.get(doc.owner_id))
        for doc in documents
    ]


def _paginate(query, page: int, limit: int):
    page = max(page, 1)
    limit = max(1, min(limit, 100))
    total = query.count()
    items = query.offset((page - 1) * limit).limit(limit).all()
    return items, {
        "page": page,
        "limit": limit,
        "total": total,
        "total_pages": ceil(total / limit) if total else 1,
    }


def _get_document_or_404(db: Session, doc_id: int) -> models.Document:
    document = db.query(models.Document).filter(models.Document.id == doc_id).first()
    if document is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu.")
    return document


def _require_owner_or_admin(document: models.Document, user: models.User) -> None:
    if not can_edit_document(document, user):
        raise HTTPException(
            status_code=403,
            detail="Bạn không có quyền thay đổi tài liệu này.",
        )


def _run_pdf_ingestion_background(
    file_path: str,
    document_id: int,
    owner_id: int,
    visibility: str,
    document_title: str,
) -> None:
    """Run ingestion with a dedicated DB session after the upload response.

    The ingestion module updates document status to processing/ready/failed and
    records each chunk in document_chunks. Errors are logged; the user can query
    GET /api/documents/{id}/status to inspect the status.
    """
    db = SessionLocal()
    try:
        from app.rag.ingestion import process_and_save_pdf

        process_and_save_pdf(
            file_path=file_path,
            document_id=str(document_id),
            owner_id=str(owner_id),
            visibility=visibility,
            document_title=document_title,
            db=db,
        )
    except Exception:
        db.rollback()
        try:
            document = (
                db.query(models.Document)
                .filter(models.Document.id == document_id)
                .first()
            )
            if document is not None:
                document.status = "failed"
                db.commit()
        except Exception:
            db.rollback()
        logger.exception("Studelytics PDF ingestion failed for document_id=%s", document_id)
    finally:
        db.close()


def _delete_document_vectors(document_id: int) -> None:
    """Best-effort vector cleanup; PostgreSQL authorization remains authoritative."""
    try:
        from app.rag.vector_store import delete_document_from_chroma

        delete_document_from_chroma(str(document_id))
    except Exception:
        logger.exception("Could not delete Chroma vectors for document_id=%s", document_id)


def _sync_visibility_to_vectors(document_id: int, visibility: str) -> int:
    """Best-effort metadata update for indexed Chroma chunks."""
    try:
        from app.rag.vector_store import update_document_visibility_in_chroma

        return int(update_document_visibility_in_chroma(str(document_id), visibility))
    except Exception:
        logger.exception("Could not update Chroma visibility for document_id=%s", document_id)
        return 0


@router.get("/dashboard")
def api_get_dashboard_data(
    page: int = Query(1, ge=1),
    limit: int = Query(12, ge=1, le=100),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    own_query = db.query(models.Document).filter(models.Document.owner_id == user.id)
    my_docs, pagination = _paginate(
        own_query.order_by(models.Document.upload_date.desc(), models.Document.id.desc()),
        page,
        limit,
    )

    shared_query = db.query(models.Document).filter(
        models.Document.visibility == "shared",
        models.Document.owner_id != user.id,
    )
    shared_docs = (
        shared_query.order_by(models.Document.upload_date.desc(), models.Document.id.desc())
        .limit(100)
        .all()
    )

    total_owned = own_query.count()
    return {
        "stats": {
            "total": total_owned,
            "public": own_query.filter(models.Document.visibility == "public").count(),
            "shared": own_query.filter(models.Document.visibility == "shared").count(),
            "private": own_query.filter(models.Document.visibility == "private").count(),
            "shared_with_me": shared_query.count(),
        },
        "pagination": pagination,
        "my_documents": _serialize_documents(my_docs, db, user),
        "shared_documents": _serialize_documents(shared_docs, db, user),
    }


@router.get("/documents")
def api_get_documents(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    user: models.User | None = Depends(get_optional_current_user),
):
    query = db.query(models.Document)
    if user is None:
        query = query.filter(models.Document.visibility == "public")
    elif not is_admin(user):
        query = query.filter(
            or_(
                models.Document.owner_id == user.id,
                models.Document.visibility.in_(["public", "shared"]),
            )
        )

    docs, pagination = _paginate(
        query.order_by(models.Document.upload_date.desc(), models.Document.id.desc()),
        page,
        limit,
    )
    return {"items": _serialize_documents(docs, db, user), "pagination": pagination}


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def api_upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str = Form(...),
    visibility: str = Form("private"),
    description: str = Form(""),
    # Accepted for compatibility with the old React Dashboard. These fields
    # are not persisted because the current Studelytics schema has no columns.
    category: str = Form("khác"),
    tags: str = Form(""),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    title = title.strip()
    if not title:
        raise HTTPException(status_code=422, detail="Tên tài liệu không được để trống.")
    if len(title) > 255:
        raise HTTPException(status_code=422, detail="Tên tài liệu không được vượt quá 255 ký tự.")
    if visibility not in VALID_VISIBILITY:
        raise HTTPException(
            status_code=422,
            detail="visibility phải là private, shared hoặc public.",
        )

    original_filename = file.filename or "document.pdf"
    if not original_filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="Chỉ hỗ trợ tải lên file PDF.")

    content = await file.read(MAX_PDF_BYTES + 1)
    if not content:
        raise HTTPException(status_code=400, detail="File tải lên đang trống.")
    if len(content) > MAX_PDF_BYTES:
        raise HTTPException(status_code=413, detail="Dung lượng PDF tối đa là 50 MB.")
    if b"%PDF-" not in content[:1024]:
        raise HTTPException(status_code=415, detail="Nội dung file không có định dạng PDF hợp lệ.")

    file_hash = hashlib.sha256(content).hexdigest()
    duplicate = (
        db.query(models.Document)
        .filter(
            models.Document.owner_id == user.id,
            models.Document.file_hash == file_hash,
        )
        .first()
    )
    if duplicate:
        raise HTTPException(
            status_code=409,
            detail=f"Bạn đã tải tài liệu này trước đó (document_id={duplicate.id}).",
        )

    upload_root = Path(UPLOAD_DIR).resolve()
    upload_root.mkdir(parents=True, exist_ok=True)
    saved_path = upload_root / f"{uuid.uuid4().hex}.pdf"
    saved_path.write_bytes(content)

    document = models.Document(
        owner_id=user.id,
        title=title,
        description=description.strip() or None,
        file_path=str(saved_path),
        file_hash=file_hash,
        total_pages=None,
        status="processing",
        visibility=visibility,
    )
    db.add(document)
    try:
        db.commit()
        db.refresh(document)
    except IntegrityError as exc:
        db.rollback()
        saved_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=409,
            detail="Bạn đã tải tài liệu này trước đó.",
        ) from exc
    except Exception:
        db.rollback()
        saved_path.unlink(missing_ok=True)
        raise

    # RAG processing begins after returning the upload response. Ingestion
    # writes Chroma vectors and document_chunks metadata, then sets status ready.
    background_tasks.add_task(
        _run_pdf_ingestion_background,
        str(saved_path),
        int(document.id),
        int(user.id),
        visibility,
        title,
    )

    response_document = _serialize_document(document, db, user)
    return {
        "message": "Đã lưu PDF. Hệ thống đang phân tích và tạo embedding.",
        "id": document.id,
        "status": document.status,
        "document": response_document,
        "metadata_note": "category/tags chỉ được nhận để tương thích giao diện; chưa lưu vào PostgreSQL.",
    }


@router.get("/documents/{doc_id}/status")
def api_get_document_status(
    doc_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    document = _get_document_or_404(db, doc_id)
    if not _can_view_document(document, user):
        raise HTTPException(status_code=403, detail="Bạn không có quyền xem trạng thái tài liệu này.")

    chunk_count = (
        db.query(models.DocumentChunk)
        .filter(models.DocumentChunk.document_id == document.id)
        .count()
    )
    return {
        "id": document.id,
        "status": document.status,
        "total_pages": document.total_pages,
        "total_chunks": chunk_count,
    }


@router.delete("/documents/{doc_id}")
def api_delete_document(
    doc_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    document = _get_document_or_404(db, doc_id)
    _require_owner_or_admin(document, user)
    file_path = document.file_path

    # Delete SQL metadata first. Foreign-key cascades remove chapters/chunks/etc.;
    # stale vectors cannot be retrieved if retrieval always authorizes via SQL.
    db.delete(document)
    db.commit()

    _delete_document_vectors(doc_id)
    try:
        if file_path and os.path.isfile(file_path):
            os.remove(file_path)
    except OSError:
        logger.exception("Document deleted from DB but file cleanup failed: %s", file_path)

    return {"message": "Đã xóa tài liệu.", "id": doc_id}


@router.patch("/documents/{doc_id}/visibility")
def update_document_visibility(
    doc_id: int,
    request: VisibilityUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    document = _get_document_or_404(db, doc_id)
    _require_owner_or_admin(document, user)
    if request.visibility not in VALID_VISIBILITY:
        raise HTTPException(status_code=422, detail="visibility phải là private, shared hoặc public.")

    old_visibility = document.visibility
    document.visibility = request.visibility
    db.commit()
    db.refresh(document)

    updated_chunks = 0
    if old_visibility != request.visibility:
        updated_chunks = _sync_visibility_to_vectors(document.id, request.visibility)

    return {
        "message": "Đã cập nhật quyền hiển thị.",
        "visibility": document.visibility,
        "updated_vector_chunks": updated_chunks,
    }


@router.get("/documents/{doc_id}/detail")
def api_get_document_detail(
    doc_id: int,
    db: Session = Depends(get_db),
    user: models.User | None = Depends(get_optional_current_user),
):
    document = _get_document_or_404(db, doc_id)
    if not _can_view_document(document, user):
        raise HTTPException(
            status_code=403 if user else 401,
            detail="Bạn không có quyền xem tài liệu này.",
        )
    return _serialize_document(document, db, user)


@router.get("/documents/{doc_id}/pdf")
def api_view_document_pdf(
    doc_id: int,
    db: Session = Depends(get_db),
    user: models.User | None = Depends(get_optional_current_user),
):
    document = _get_document_or_404(db, doc_id)
    if not _can_view_document(document, user):
        raise HTTPException(
            status_code=403 if user else 401,
            detail="Bạn không có quyền xem tài liệu này.",
        )
    if not document.file_path or not os.path.isfile(document.file_path):
        raise HTTPException(status_code=404, detail="File PDF không còn tồn tại trên máy chủ.")

    return FileResponse(
        document.file_path,
        media_type="application/pdf",
        filename=f"{document.title}.pdf",
        content_disposition_type="inline",
    )


@router.post("/documents/{doc_id}/summarize")
def api_summarize_document(
    doc_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    document = _get_document_or_404(db, doc_id)
    if not _can_view_document(document, user):
        raise HTTPException(status_code=403, detail="Bạn không có quyền xem tài liệu này.")
    if document.status != "ready":
        raise HTTPException(
            status_code=409,
            detail=f"Tài liệu chưa xử lý xong (status={document.status}). Hãy thử lại sau.",
        )

    try:
        from app.rag.summarization import summarize_pdf

        summary = summarize_pdf(document.file_path)
    except Exception as exc:
        logger.exception("Summarization failed for document_id=%s", doc_id)
        raise HTTPException(
            status_code=503,
            detail="Chưa thể tóm tắt tài liệu. Kiểm tra GROQ_API_KEY và các thư viện RAG.",
        ) from exc

    return {"document_id": document.id, "title": document.title, "summary": summary}


@router.post("/documents/{doc_id}/share")
def share_document(
    doc_id: int,
    request: ShareDocumentRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    document = _get_document_or_404(db, doc_id)
    _require_owner_or_admin(document, user)
    raise HTTPException(
        status_code=501,
        detail=(
            "Database hiện chưa có bảng chia sẻ theo từng người. "
            "Bạn có thể đặt visibility='shared' để cho phép người dùng đã đăng nhập xem tài liệu."
        ),
    )


@router.get("/documents/{doc_id}/shared-with")
def get_shared_users(
    doc_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    document = _get_document_or_404(db, doc_id)
    _require_owner_or_admin(document, user)
    if document.visibility == "shared":
        return {
            "visibility": "shared",
            "sharing_policy": "all_authenticated_users",
            "users": None,
        }
    return {
        "visibility": document.visibility,
        "sharing_policy": "not_shared_with_specific_users",
        "users": [],
    }


@router.patch("/documents/{doc_id}/share/{user_id}")
def update_share_permission(
    doc_id: int,
    user_id: int,
    request: SharePermissionUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    document = _get_document_or_404(db, doc_id)
    _require_owner_or_admin(document, user)
    raise HTTPException(
        status_code=501,
        detail="Phân quyền chia sẻ theo từng người chưa được hỗ trợ trong schema hiện tại.",
    )


@router.delete("/documents/{doc_id}/share/{user_id}")
def revoke_share(
    doc_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    document = _get_document_or_404(db, doc_id)
    _require_owner_or_admin(document, user)
    raise HTTPException(
        status_code=501,
        detail="Thu hồi chia sẻ theo từng người chưa được hỗ trợ trong schema hiện tại.",
    )


@router.get("/shared-with-me")
def shared_with_me(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    docs = (
        db.query(models.Document)
        .filter(
            models.Document.visibility == "shared",
            models.Document.owner_id != user.id,
        )
        .order_by(models.Document.upload_date.desc(), models.Document.id.desc())
        .all()
    )
    return {
        "items": _serialize_documents(docs, db, user),
        "sharing_policy": "all_authenticated_users",
    }
