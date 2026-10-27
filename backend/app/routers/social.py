from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.services.document_access import serialize_document
from app.services.security import get_current_user, get_optional_current_user

router = APIRouter(prefix="/api/documents", tags=["social"])


def _requires_social_tables() -> None:
    raise HTTPException(
        status_code=501,
        detail="Bình luận và upvote chưa được hỗ trợ vì schema Studelytics hiện chưa có bảng comments/upvotes.",
    )


@router.get("/trending")
def get_trending_documents(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    user=Depends(get_optional_current_user),
):
    # The current schema has no views/upvotes/comments counters. Return the most recently uploaded public items.
    docs = db.query(models.Document).filter(
        models.Document.visibility == "public"
    ).order_by(models.Document.upload_date.desc(), models.Document.id.desc()).limit(limit).all()
    return [serialize_document(doc, db, user) for doc in docs]


@router.post("/{doc_id}/upvote")
def toggle_upvote(doc_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    exists = db.query(models.Document.id).filter(models.Document.id == doc_id).first()
    if not exists:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu.")
    _requires_social_tables()


@router.get("/{doc_id}/comments")
def get_comments(doc_id: int, db: Session = Depends(get_db), user=Depends(get_optional_current_user)):
    exists = db.query(models.Document.id).filter(models.Document.id == doc_id).first()
    if not exists:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu.")
    _requires_social_tables()


@router.post("/{doc_id}/comments")
def post_comment(doc_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    exists = db.query(models.Document.id).filter(models.Document.id == doc_id).first()
    if not exists:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu.")
    _requires_social_tables()


@router.delete("/{doc_id}/comments/{comment_id}")
def delete_comment(doc_id: int, comment_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    exists = db.query(models.Document.id).filter(models.Document.id == doc_id).first()
    if not exists:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu.")
    _requires_social_tables()
