from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models

ALLOWED_VISIBILITIES = {"private", "shared", "public"}
CHUNK_SIZE = 1024 * 1024  # 1 MiB


def can_view_document(
    doc: models.Document | None,
    user: models.User | None,
    db: Session | None = None,
) -> bool:

    if doc is None:
        return False

    visibility = (getattr(doc, "visibility", "private") or "private").lower()
    if visibility == "public":
        return True

    if user is None or not getattr(user, "is_active", False):
        return False

    if getattr(user, "role", None) == "admin":
        return True

    if getattr(doc, "owner_id", None) == getattr(user, "id", None):
        return True

    return visibility == "shared"


def _get_owner(doc: models.Document, db: Session | None) -> models.User | None:
    """Load owner by FK; the Studelytics ORM models need not define a relation."""
    if db is None or getattr(doc, "owner_id", None) is None:
        return None
    return (
        db.query(models.User)
        .filter(models.User.id == doc.owner_id)
        .first()
    )


def serialize_document(
    doc: models.Document,
    *,
    include_social: bool = False,
    db: Session | None = None,
    user: models.User | None = None,
) -> dict[str, Any]:
    owner = _get_owner(doc, db)
    uploaded_at = getattr(doc, "upload_date", None)
    role = getattr(user, "role", None) if user else None
    is_owner = bool(user and getattr(doc, "owner_id", None) == user.id)
