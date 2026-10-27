from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.schemas.chat import ChatRequest
from app.services.document_access import can_view_document
from app.services.security import get_current_user

router = APIRouter(prefix="/api", tags=["chat"])


def make_conversation_title(question: str) -> str:
    clean = " ".join((question or "").strip().split())
    if not clean:
        return "Cuộc trò chuyện mới"
    return clean[:252].rstrip() + ("..." if len(clean) > 255 else "")


def _selected_ids(request: ChatRequest) -> list[int]:
    values: list[str] = []
    for value in request.document_ids or []:
        value = str(value).strip()
        if value and value.lower() != "all" and value not in values:
            values.append(value)
    if not values and request.document_id and str(request.document_id).lower() != "all":
        values = [str(request.document_id).strip()]
    try:
        return [int(value) for value in values]
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="document_id phải là số nguyên hợp lệ.") from exc


def _validate_document_access(db: Session, user: models.User, document_ids: list[int]) -> None:
    for document_id in document_ids:
        doc = db.query(models.Document).filter(models.Document.id == document_id).first()
        if doc is None:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy tài liệu {document_id}.")
        if not can_view_document(doc, user):
            raise HTTPException(status_code=403, detail=f"Bạn không có quyền truy cập tài liệu {document_id}.")


def _serialize_conversation(conversation: models.Conversation) -> dict:
    return {
        "id": conversation.id,
        "title": conversation.title,
        "document_id": str(conversation.document_id) if conversation.document_id is not None else "all",
        "document_ids": [str(conversation.document_id)] if conversation.document_id is not None else [],
        "chapter_id": conversation.chapter_id,
        "created_at": conversation.created_at.isoformat() if conversation.created_at else None,
    }


@router.post("/conversations", status_code=201)
def create_conversation(
    request: ChatRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    selected_ids = _selected_ids(request)
    _validate_document_access(db, user, selected_ids)

    document_id = selected_ids[0] if len(selected_ids) == 1 else None
    chapter_id = request.chapter_id
    if chapter_id is not None:
        if document_id is None:
            raise HTTPException(status_code=422, detail="Chọn đúng một tài liệu khi tạo hội thoại theo chương.")
        chapter = db.query(models.Chapter).filter(
            models.Chapter.id == chapter_id,
            models.Chapter.document_id == document_id,
        ).first()
        if chapter is None:
            raise HTTPException(status_code=404, detail="Không tìm thấy chương trong tài liệu đã chọn.")

    conversation = models.Conversation(
        user_id=user.id,
        document_id=document_id,
        chapter_id=chapter_id,
        title=make_conversation_title(request.question),
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    result = _serialize_conversation(conversation)
    result["document_ids"] = [str(item) for item in selected_ids]
    return result


@router.post("/chat")
def api_chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    selected_ids = _selected_ids(request)
    _validate_document_access(db, user, selected_ids)
    if request.conversation_id:
        conversation = db.query(models.Conversation).filter(
            models.Conversation.id == request.conversation_id,
            models.Conversation.user_id == user.id,
        ).first()
        if conversation is None:
            raise HTTPException(status_code=404, detail="Không tìm thấy phiên chat.")
    raise HTTPException(
        status_code=501,
        detail=(
            "Chat RAG chưa được nối vào pipeline Studelytics. Bước tiếp theo là triển khai "
            "PDF Parser, chunking, embeddings và retrieval trước khi bật trả lời AI."
        ),
    )


@router.get("/conversations")
def get_conversations(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    rows = db.query(models.Conversation).filter(
        models.Conversation.user_id == user.id
    ).order_by(models.Conversation.created_at.desc(), models.Conversation.id.desc()).all()
    return [_serialize_conversation(row) for row in rows]


@router.get("/conversations/{conv_id}/messages")
def get_messages(
    conv_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    conversation = db.query(models.Conversation).filter(
        models.Conversation.id == conv_id,
        models.Conversation.user_id == user.id,
    ).first()
    if conversation is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên chat.")

    messages = db.query(models.ChatHistory).filter(
        models.ChatHistory.conversation_id == conv_id
    ).order_by(models.ChatHistory.created_at.asc(), models.ChatHistory.id.asc()).all()

    result = []
    for message in messages:
        result.append({
            "id": f"{message.id}-user",
            "sender": "user",
            "text": message.question,
            "created_at": message.created_at.isoformat() if message.created_at else None,
        })
        result.append({
            "id": f"{message.id}-ai",
            "sender": "ai",
            "text": message.answer,
            "citations": message.citations or [],
            "sources": message.retrieved_chunks or [],
            "created_at": message.created_at.isoformat() if message.created_at else None,
        })
    return result


@router.delete("/conversations/{conv_id}")
def delete_conversation(
    conv_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    conversation = db.query(models.Conversation).filter(
        models.Conversation.id == conv_id,
        models.Conversation.user_id == user.id,
    ).first()
    if conversation is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên chat.")
    db.delete(conversation)
    db.commit()  # chat_history is removed by ON DELETE CASCADE
    return {"message": "Đã xóa phiên chat."}
