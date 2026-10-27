from collections import OrderedDict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.services.document_access import can_view_document
from app.services.security import get_current_user

router = APIRouter(prefix="/api", tags=["flashcards"])


class FlashcardCreatePayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    document_id: int | None = None
    chapter_id: int | None = None
    front: str | None = None
    back: str | None = None
    front_text: str | None = None
    back_text: str | None = None


class FlashcardUpdatePayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    front: str | None = None
    back: str | None = None
    front_text: str | None = None
    back_text: str | None = None


class SaveCardsPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    cards: list[Any]


def _card_to_dict(card: models.Flashcard, db: Session) -> dict:
    document = db.query(models.Document).filter(models.Document.id == card.document_id).first()
    return {
        "id": card.id,
        "document_id": card.document_id,
        "document_title": document.title if document else None,
        "chapter_id": card.chapter_id,
        "front": card.front,
        "back": card.back,
        # Old frontend field names retained as response aliases.
        "front_text": card.front,
        "back_text": card.back,
        "source_page": card.source_page,
        "source_chunk_id": card.source_chunk_id,
        "created_at": card.created_at.isoformat() if card.created_at else None,
    }


def _normalize_card(item: Any) -> dict | None:
    if hasattr(item, "model_dump"):
        item = item.model_dump()
    elif hasattr(item, "dict"):
        item = item.dict()
    if not isinstance(item, dict):
        return None
    front = item.get("front") or item.get("front_text") or item.get("question") or item.get("term") or item.get("q")
    back = item.get("back") or item.get("back_text") or item.get("answer") or item.get("definition") or item.get("a")
    if front is None or back is None:
        return None
    front, back = str(front).strip(), str(back).strip()
    if not front or not back:
        return None
    raw_page = item.get("source_page")
    try:
        source_page = int(raw_page) if raw_page is not None else None
        if source_page is not None and source_page <= 0:
            source_page = None
    except (TypeError, ValueError):
        source_page = None
    def _positive_int(raw_value):
        try:
            value = int(raw_value) if raw_value is not None else None
            return value if value is not None and value > 0 else None
        except (TypeError, ValueError):
            return None
    return {
        "front": front[:10000],
        "back": back[:20000],
        "source_page": source_page,
        "chapter_id": _positive_int(item.get("chapter_id")),
        "source_chunk_id": _positive_int(item.get("source_chunk_id")),
    }


def _get_accessible_document(db: Session, user: models.User, doc_id: int) -> models.Document:
    doc = db.query(models.Document).filter(models.Document.id == doc_id).first()
    if doc is None or not can_view_document(doc, user):
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu hoặc bạn không có quyền xem.")
    return doc


def _save_cards(db: Session, user: models.User, doc_id: int, cards: list[Any], replace: bool) -> list[models.Flashcard]:
    clean_cards = [normalized for item in cards if (normalized := _normalize_card(item))]
    if not clean_cards:
        raise HTTPException(status_code=422, detail="Không có flashcard hợp lệ để lưu.")

    _get_accessible_document(db, user, doc_id)
    if replace:
        db.query(models.Flashcard).filter(
            models.Flashcard.user_id == user.id,
            models.Flashcard.document_id == doc_id,
        ).delete(synchronize_session=False)

    rows = []
    for item in clean_cards:
        chapter_id = item["chapter_id"]
        if chapter_id is not None:
            chapter = db.query(models.Chapter).filter(
                models.Chapter.id == chapter_id,
                models.Chapter.document_id == doc_id,
            ).first()
            if chapter is None:
                raise HTTPException(status_code=422, detail="chapter_id không thuộc tài liệu đã chọn.")
        source_chunk_id = item["source_chunk_id"]
        if source_chunk_id is not None:
            chunk = db.query(models.DocumentChunk.id).filter(
                models.DocumentChunk.id == source_chunk_id,
                models.DocumentChunk.document_id == doc_id,
            ).first()
            if chunk is None:
                source_chunk_id = None
        row = models.Flashcard(
            user_id=user.id,
            document_id=doc_id,
            chapter_id=chapter_id,
            front=item["front"],
            back=item["back"],
            source_page=item["source_page"],
            source_chunk_id=source_chunk_id,
        )
        db.add(row)
        rows.append(row)
    db.commit()
    for row in rows:
        db.refresh(row)
    return rows


@router.get("/flashcards")
def api_get_flashcards(
    document_id: int | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    query = db.query(models.Flashcard).filter(models.Flashcard.user_id == user.id)
    if document_id is not None:
        query = query.filter(models.Flashcard.document_id == document_id)
    rows = query.order_by(models.Flashcard.created_at.asc(), models.Flashcard.id.asc()).all()
    return [_card_to_dict(row, db) for row in rows]


@router.get("/flashcard-sets")
def api_get_flashcard_sets(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    rows = db.query(models.Flashcard).filter(
        models.Flashcard.user_id == user.id
    ).order_by(models.Flashcard.created_at.desc(), models.Flashcard.id.desc()).all()
    grouped: OrderedDict[int, dict] = OrderedDict()
    for card in rows:
        doc = db.query(models.Document).filter(models.Document.id == card.document_id).first()
        key = card.document_id
        if key not in grouped:
            grouped[key] = {
                "document_id": key,
                "document_title": doc.title if doc else "Tài liệu đã xóa",
                "count": 0,
                "latest_created_at": card.created_at.isoformat() if card.created_at else None,
            }
        grouped[key]["count"] += 1
    return list(grouped.values())


@router.post("/flashcards", status_code=status.HTTP_201_CREATED)
def api_create_flashcard(
    request: FlashcardCreatePayload,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    if request.document_id is None:
        raise HTTPException(status_code=422, detail="document_id là bắt buộc theo schema Studelytics.")
    normalized = _normalize_card(request.model_dump())
    if normalized is None:
        raise HTTPException(status_code=422, detail="Cần cung cấp front/back hoặc front_text/back_text.")
    saved = _save_cards(db, user, request.document_id, [{**normalized, "chapter_id": request.chapter_id}], replace=False)
    return _card_to_dict(saved[0], db)


@router.patch("/flashcards/{card_id}")
def api_update_flashcard(
    card_id: int,
    request: FlashcardUpdatePayload,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    card = db.query(models.Flashcard).filter(
        models.Flashcard.id == card_id,
        models.Flashcard.user_id == user.id,
    ).first()
    if card is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy flashcard.")
    front = request.front if request.front is not None else request.front_text
    back = request.back if request.back is not None else request.back_text
    if front is not None:
        if not front.strip():
            raise HTTPException(status_code=422, detail="Mặt trước không được để trống.")
        card.front = front.strip()
    if back is not None:
        if not back.strip():
            raise HTTPException(status_code=422, detail="Mặt sau không được để trống.")
        card.back = back.strip()
    db.commit()
    db.refresh(card)
    return _card_to_dict(card, db)


@router.delete("/flashcards/{card_id}")
def api_delete_flashcard(card_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    card = db.query(models.Flashcard).filter(
        models.Flashcard.id == card_id,
        models.Flashcard.user_id == user.id,
    ).first()
    if card is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy flashcard.")
    db.delete(card)
    db.commit()
    return {"message": "Đã xóa flashcard."}


@router.delete("/documents/{doc_id}/flashcards")
def api_delete_flashcard_set(doc_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    deleted = db.query(models.Flashcard).filter(
        models.Flashcard.user_id == user.id,
        models.Flashcard.document_id == doc_id,
    ).delete(synchronize_session=False)
    db.commit()
    return {"message": "Đã xóa bộ flashcard.", "count": deleted}


@router.post("/documents/{doc_id}/flashcards/generate")
def generate_document_flashcards(doc_id: int, count: int = Query(12, ge=1, le=100), db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    _get_accessible_document(db, user, doc_id)
    raise HTTPException(status_code=501, detail="Tạo flashcard tự động sẽ được bật sau khi tích hợp PDF Parser và AI generation.")


@router.post("/documents/{doc_id}/flashcards/save")
def save_document_flashcards(
    doc_id: int,
    request: SaveCardsPayload,
    replace: bool = Query(True),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    saved = _save_cards(db, user, doc_id, request.cards, replace)
    doc = db.query(models.Document).filter(models.Document.id == doc_id).first()
    return {
        "message": f"Đã lưu {len(saved)} flashcard.",
        "count": len(saved),
        "document_id": doc_id,
        "document_title": doc.title if doc else None,
        "cards": [_card_to_dict(card, db) for card in saved],
    }


@router.post("/documents/{doc_id}/flashcards/generate-and-save")
def generate_and_save_document_flashcards(
    doc_id: int,
    count: int = Query(12, ge=1, le=100),
    replace: bool = Query(True),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    _get_accessible_document(db, user, doc_id)
    raise HTTPException(status_code=501, detail="Tạo flashcard tự động sẽ được bật sau khi tích hợp PDF Parser và AI generation.")


@router.get("/documents/{doc_id}/flashcards")
def get_document_flashcards(doc_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    _get_accessible_document(db, user, doc_id)
    rows = db.query(models.Flashcard).filter(
        models.Flashcard.document_id == doc_id,
        models.Flashcard.user_id == user.id,
    ).order_by(models.Flashcard.created_at.asc(), models.Flashcard.id.asc()).all()
    return [_card_to_dict(row, db) for row in rows]
