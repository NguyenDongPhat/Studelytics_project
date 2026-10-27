from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.schemas.users import UpdatePasswordRequest, UpdateProfileRequest, UserSettingsUpdate
from app.services.security import get_current_user, hash_password, verify_password

router = APIRouter(prefix="/api/users", tags=["users"])


def serialize_user(user: models.User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


@router.get("/me")
def api_get_me(user: models.User = Depends(get_current_user)):
    return serialize_user(user)


@router.patch("/me/profile")
def api_update_profile(
    request: UpdateProfileRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    username = request.username.strip()
    if len(username) < 3 or len(username) > 50:
        raise HTTPException(status_code=422, detail="Tên người dùng phải từ 3 đến 50 ký tự.")

    existing = db.query(models.User).filter(
        func.lower(models.User.username) == username.lower(),
        models.User.id != user.id,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Tên người dùng đã tồn tại.")

    user.username = username
    try:
        db.commit()
        db.refresh(user)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Tên người dùng đã tồn tại.") from exc
    return {"message": "Cập nhật hồ sơ thành công.", "user": serialize_user(user)}


@router.patch("/me/password")
def api_update_password(
    request: UpdatePasswordRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    if not verify_password(request.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Mật khẩu hiện tại không đúng.")
    user.password_hash = hash_password(request.new_password)
    db.commit()
    return {"message": "Mật khẩu đã được cập nhật."}


@router.get("/me/settings")
def get_user_settings(user: models.User = Depends(get_current_user)):
    # Intentionally no DB query: the current 14-table schema has no user_settings table.
    raise HTTPException(
        status_code=501,
        detail="Cài đặt cá nhân chưa được hỗ trợ trong schema Studelytics hiện tại.",
    )


@router.patch("/me/settings")
def update_user_settings(
    request: UserSettingsUpdate,
    user: models.User = Depends(get_current_user),
):
    raise HTTPException(
        status_code=501,
        detail="Không thể lưu cài đặt cá nhân vì schema hiện tại chưa có bảng user_settings.",
    )


@router.delete("/me/chats/clear")
def clear_my_chats(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    deleted = db.query(models.Conversation).filter(
        models.Conversation.user_id == user.id
    ).delete(synchronize_session=False)
    # chat_history rows are removed by ON DELETE CASCADE in PostgreSQL.
    db.commit()
    return {"message": "Đã xóa lịch sử chat.", "deleted_conversations": deleted}
