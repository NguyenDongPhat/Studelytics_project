import os
from datetime import datetime, timedelta, timezone
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.services.document_access import serialize_document
from app.services.security import get_current_admin, is_admin

router = APIRouter(prefix="/api/admin", tags=["admin"])


class AdminVisibilityUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    visibility: str = Field(pattern="^(private|shared|public)$")


class BulkDeleteCommentsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ids: list[int] = Field(default_factory=list)


def _pagination(page: int, limit: int, total: int) -> dict:
    return {"page": page, "limit": limit, "total": total, "total_pages": ceil(total / limit) if total else 1}


def _serialize_user(user: models.User, db: Session) -> dict:
    role_labels = {"user": "Người dùng", "admin": "Quản trị viên"}
    documents_count = db.query(models.Document).filter(models.Document.owner_id == user.id).count()
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "role_label": role_labels.get(user.role, user.role),
        "is_active": user.is_active,
        "is_banned": not user.is_active,  # response alias for legacy admin UI
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "documents_count": documents_count,
    }


def _get_document(db: Session, doc_id: int) -> models.Document:
    doc = db.query(models.Document).filter(models.Document.id == doc_id).first()
    if doc is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu.")
    return doc


def _delete_document_file(document: models.Document) -> None:
    try:
        if document.file_path and os.path.isfile(document.file_path):
            os.remove(document.file_path)
    except OSError:
        # Leave an orphaned file for later cleanup rather than failing the DB operation.
        pass


@router.get("/stats")
def get_admin_stats(db: Session = Depends(get_db), admin: models.User = Depends(get_current_admin)):
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=7)
    total_users = db.query(models.User).count()
    active_users = db.query(models.User).filter(models.User.is_active.is_(True)).count()
    inactive_users = db.query(models.User).filter(models.User.is_active.is_(False)).count()
    total_docs = db.query(models.Document).count()
    return {
        "users": total_users,
        "active_users": active_users,
        "inactive_users": inactive_users,
        "banned_users": inactive_users,
        "regular_users": db.query(models.User).filter(models.User.role == "user").count(),
        "admins": db.query(models.User).filter(models.User.role == "admin").count(),
        "documents": total_docs,
        "public_documents": db.query(models.Document).filter(models.Document.visibility == "public").count(),
        "shared_documents": db.query(models.Document).filter(models.Document.visibility == "shared").count(),
        "private_documents": db.query(models.Document).filter(models.Document.visibility == "private").count(),
        "processing_documents": db.query(models.Document).filter(models.Document.status == "processing").count(),
        "failed_documents": db.query(models.Document).filter(models.Document.status == "failed").count(),
        "new_users_7d": db.query(models.User).filter(models.User.created_at >= since).count(),
        "new_docs_7d": db.query(models.Document).filter(models.Document.upload_date >= since).count(),
    }


@router.get("/users")
def get_all_users(
    q: str = "",
    role: str = Query("all", pattern="^(all|user|admin|inactive|banned|active)$"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_admin),
):
    query = db.query(models.User)
    if q.strip():
        keyword = f"%{q.strip()}%"
        query = query.filter(or_(models.User.username.ilike(keyword), models.User.email.ilike(keyword)))
    if role == "user":
        query = query.filter(models.User.role == "user")
    elif role == "admin":
        query = query.filter(models.User.role == "admin")
    elif role in {"inactive", "banned"}:
        query = query.filter(models.User.is_active.is_(False))
    elif role == "active":
        query = query.filter(models.User.is_active.is_(True))

    total = query.count()
    rows = query.order_by(models.User.id.desc()).offset((page - 1) * limit).limit(limit).all()
    return {"items": [_serialize_user(row, db) for row in rows], **_pagination(page, limit, total)}


@router.patch("/users/{user_id}/ban")
def ban_user(user_id: int, db: Session = Depends(get_db), admin: models.User = Depends(get_current_admin)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng.")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Không thể tự vô hiệu hóa tài khoản quản trị của mình.")
    if is_admin(user):
        raise HTTPException(status_code=403, detail="Không thể vô hiệu hóa tài khoản admin khác qua chức năng này.")
    user.is_active = False
    db.commit()
    return {"message": "Đã vô hiệu hóa tài khoản.", "user_id": user.id, "is_active": user.is_active}


@router.patch("/users/{user_id}/unban")
def unban_user(user_id: int, db: Session = Depends(get_db), admin: models.User = Depends(get_current_admin)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng.")
    user.is_active = True
    db.commit()
    return {"message": "Đã kích hoạt lại tài khoản.", "user_id": user.id, "is_active": user.is_active}


@router.get("/documents")
def get_admin_documents(
    q: str = "",
    visibility: str = "all",
    document_status: str = Query("all", alias="status"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_admin),
):
    query = db.query(models.Document)
    if visibility in {"private", "shared", "public"}:
        query = query.filter(models.Document.visibility == visibility)
    if document_status in {"uploaded", "processing", "ready", "failed"}:
        query = query.filter(models.Document.status == document_status)
    if q.strip():
        keyword = f"%{q.strip()}%"
        query = query.join(models.User, models.Document.owner_id == models.User.id).filter(
            or_(
                models.Document.title.ilike(keyword),
                models.Document.description.ilike(keyword),
                models.User.username.ilike(keyword),
                models.User.email.ilike(keyword),
            )
        )
    total = query.count()
    rows = query.order_by(models.Document.id.desc()).offset((page - 1) * limit).limit(limit).all()
    return {
        "items": [serialize_document(doc, db, admin) for doc in rows],
        **_pagination(page, limit, total),
    }


@router.patch("/documents/{doc_id}/visibility")
def admin_update_document_visibility(
    doc_id: int,
    request: AdminVisibilityUpdate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_admin),
):
    doc = _get_document(db, doc_id)
    doc.visibility = request.visibility
    db.commit()
    db.refresh(doc)
    return {"message": "Đã cập nhật quyền hiển thị tài liệu.", "visibility": doc.visibility}


@router.delete("/documents/{doc_id}")
def admin_delete_document(doc_id: int, db: Session = Depends(get_db), admin: models.User = Depends(get_current_admin)):
    doc = _get_document(db, doc_id)
    file_path = doc.file_path
    db.delete(doc)
    db.commit() 
    try:
        if file_path and os.path.isfile(file_path):
            os.remove(file_path)
    except OSError:
        pass
    return {"message": "Đã xóa tài liệu.", "id": doc_id}


@router.get("/comments")
def get_admin_comments(admin: models.User = Depends(get_current_admin)):
    raise HTTPException(status_code=501, detail="Schema Studelytics hiện chưa có bảng comments.")


@router.delete("/comments/{comment_id}")
def admin_delete_comment(comment_id: int, admin: models.User = Depends(get_current_admin)):
    raise HTTPException(status_code=501, detail="Schema Studelytics hiện chưa có bảng comments.")


@router.post("/comments/bulk-delete")
def admin_bulk_delete_comments(request: BulkDeleteCommentsRequest, admin: models.User = Depends(get_current_admin)):
    raise HTTPException(status_code=501, detail="Schema Studelytics hiện chưa có bảng comments.")
