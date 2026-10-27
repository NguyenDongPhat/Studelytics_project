from __future__ import annotations

from typing import Any

from app import models
from app.services.security import is_admin


def can_view_document(document: models.Document, user: models.User | None) -> bool:
    if document.visibility == "public":
        return True
    if user is None or not getattr(user, "is_active", False):
        return False
    if is_admin(user) or document.owner_id == user.id:
        return True
    return document.visibility == "shared"


def can_edit_document(document: models.Document, user: models.User | None) -> bool:
    if user is None or not getattr(user, "is_active", False):
        return False
    return document.owner_id == user.id or is_admin(user)


def serialize_document(
    document: models.Document,
    db,
    user: models.User | None = None,
    owner: models.User | None = None,
) -> dict[str, Any]:
    if owner is None:
        owner = db.query(models.User).filter(models.User.id == document.owner_id).first()

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
        "is_owner": bool(user and document.owner_id == user.id),
        "can_edit": can_edit_document(document, user),
        "can_view": can_view_document(document, user),
        "category": None,
        "tags": [],
        "views": 0,
    }
