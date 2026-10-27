from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.core.config import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    COOKIE_SECURE,
    JWT_ALGORITHM,
    JWT_SECRET_KEY,
)
from app.database import get_db
from app.schemas.auth import LoginRequest, RegisterRequest
from app.services.security import decode_access_token, hash_password, verify_password
from jose import jwt

router = APIRouter(prefix="/api", tags=["Authentication"])


def user_payload(user: models.User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def create_access_token(user: models.User) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": user.email,
        "user_id": user.id,
        "role": user.role,
        "exp": expires_at,
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )


@router.post("/register", status_code=status.HTTP_201_CREATED)
def api_register(request: RegisterRequest, db: Session = Depends(get_db)):
    username = request.username.strip()
    email = request.email.strip().lower()
    password = request.password

    existing = db.query(models.User).filter(
        or_(
            func.lower(models.User.email) == email,
            func.lower(models.User.username) == username.lower(),
        )
    ).first()
    if existing:
        if existing.email.lower() == email:
            raise HTTPException(status_code=409, detail="Email đã được sử dụng.")
        raise HTTPException(status_code=409, detail="Tên người dùng đã tồn tại.")

    user = models.User(
        username=username,
        email=email,
        password_hash=hash_password(password),
        role="user",
        is_active=True,
    )
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Email hoặc tên người dùng đã tồn tại.") from exc

    return {"message": "Đăng ký tài khoản thành công.", "user": user_payload(user)}


@router.post("/login")
def api_login(
    request: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    email = request.email.strip().lower()
    user = db.query(models.User).filter(func.lower(models.User.email) == email).first()

    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email hoặc mật khẩu không đúng.",
        )
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Tài khoản đã bị vô hiệu hóa.")

    token = create_access_token(user)
    set_auth_cookie(response, token)
    return {
        "message": "Đăng nhập thành công.",
        "access_token": token,
        "token_type": "bearer",
        "user": user_payload(user),
    }


@router.post("/logout")
def api_logout(response: Response):
    response.delete_cookie(
        key="access_token",
        path="/",
        secure=COOKIE_SECURE,
        httponly=True,
        samesite="lax",
    )
    return {"message": "Đăng xuất thành công."}


def decode_token(token: str) -> dict:
    return decode_access_token(token)
