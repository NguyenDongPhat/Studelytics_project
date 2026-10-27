from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.services.document_access import serialize_document
from app.services.security import get_optional_current_user, is_admin

router = APIRouter(prefix="/api", tags=["search"])


def pagination_meta(page: int, limit: int, total: int) -> dict:
    return {
        "page": page,
        "limit": limit,
        "total": total,
        "total_pages": ceil(total / limit) if total else 1,
    }


@router.get("/public-documents")
def api_get_public_documents(
    page: int = Query(1, ge=1),
    limit: int = Query(12, ge=1, le=100),
    q: str = "",
    db: Session = Depends(get_db),
    user=Depends(get_optional_current_user),
):
    query = db.query(models.Document).filter(models.Document.visibility == "public")
    if q.strip():
        keyword = f"%{q.strip()}%"
        query = query.filter(
            or_(models.Document.title.ilike(keyword), models.Document.description.ilike(keyword))
        )
    total = query.count()
    docs = query.order_by(models.Document.upload_date.desc(), models.Document.id.desc()).offset((page - 1) * limit).limit(limit).all()
    return {
        "items": [serialize_document(doc, db, user) for doc in docs],
        "pagination": pagination_meta(page, limit, total),
    }


@router.get("/search")
def api_search_documents(
    q: str = Query(..., min_length=1, max_length=255),
    scope: str = Query("all", pattern="^(all|documents|public|shared)$"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user=Depends(get_optional_current_user),
):
    query_text = q.strip()
    if not query_text:
        return {"items": [], "pagination": pagination_meta(page, limit, 0)}

    if scope == "documents" and user is None:
        raise HTTPException(status_code=401, detail="Đăng nhập để tìm trong tài liệu cá nhân.")
    if scope == "shared" and user is None:
        raise HTTPException(status_code=401, detail="Đăng nhập để tìm tài liệu dùng chung.")

    query = db.query(models.Document)
    if user is None:
        query = query.filter(models.Document.visibility == "public")
    elif not is_admin(user):
        if scope == "documents":
            query = query.filter(models.Document.owner_id == user.id)
        elif scope == "public":
            query = query.filter(models.Document.visibility == "public")
        elif scope == "shared":
            query = query.filter(models.Document.visibility == "shared")
        else:
            query = query.filter(
                or_(
                    models.Document.owner_id == user.id,
                    models.Document.visibility.in_(["public", "shared"]),
                )
            )
    elif scope == "documents":
        query = query.filter(models.Document.owner_id == user.id)
    elif scope == "public":
        query = query.filter(models.Document.visibility == "public")
    elif scope == "shared":
        query = query.filter(models.Document.visibility == "shared")

    keyword = f"%{query_text}%"
    query = query.filter(
        or_(models.Document.title.ilike(keyword), models.Document.description.ilike(keyword))
    )
    docs = query.order_by(models.Document.upload_date.desc(), models.Document.id.desc()).all()

    results = []
    query_lower = query_text.lower()
    for doc in docs:
        score = 1.0
        if doc.title and query_lower in doc.title.lower():
            score += 1.0
        if doc.description and query_lower in doc.description.lower():
            score += 0.5
        item = serialize_document(doc, db, user)
        item["relevance_score"] = score
        results.append(item)
    results.sort(key=lambda item: (item["relevance_score"], item.get("upload_date") or ""), reverse=True)

    total = len(results)
    start = (page - 1) * limit
    return {"items": results[start:start + limit], "pagination": pagination_meta(page, limit, total)}
