from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import (
    InvalidHashError,
    VerificationError,
    VerifyMismatchError,
)
from fastapi import Cookie, Depends, Header, HTTPException, status
from jose import JWTError, jwt
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models
from app.core.config import JWT_ALGORITHM, JWT_SECRET_KEY
from app.database import get_db


_password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Hash a plaintext password using Argon2."""
    return _password_hasher.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Return True when the password matches its stored hash."""
    try:
        return _password_hasher.verify(password_hash, plain_password)
    except (
        VerifyMismatchError,
        VerificationError,
        InvalidHashError,
        TypeError,
    ):
        return False


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT access token."""
    try:
        return jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token không hợp lệ hoặc đã hết hạn.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def _extract_token(
    access_token: str | None,
    authorization: str | None,
) -> str | None:
    if authorization:
        scheme, separator, credentials = authorization.partition(" ")
        if separator and scheme.lower() == "bearer" and credentials.strip():
            return credentials.strip()

    return access_token


def _get_user_from_token(token: str, db: Session) -> models.User:
    payload = decode_access_token(token)

    user_id = payload.get("user_id")
    subject = payload.get("sub")

    query = db.query(models.User)

    if user_id is not None:
        user = query.filter(models.User.id == user_id).first()
    elif isinstance(subject, str) and subject.strip():
        user = query.filter(
            func.lower(models.User.email) == subject.strip().lower()
        ).first()
    else:
        user = None

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Không tìm thấy tài khoản của phiên đăng nhập.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản đã bị vô hiệu hóa.",
        )

    return user


def get_current_user(
    db: Session = Depends(get_db),
    access_token: str | None = Cookie(default=None),
    authorization: str | None = Header(default=None),
) -> models.User:
    token = _extract_token(access_token, authorization)

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bạn cần đăng nhập để sử dụng chức năng này.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return _get_user_from_token(token, db)


def get_optional_current_user(
    db: Session = Depends(get_db),
    access_token: str | None = Cookie(default=None),
    authorization: str | None = Header(default=None),
) -> models.User | None:
    """Return the authenticated user, or None when no token is provided."""
    token = _extract_token(access_token, authorization)

    if not token:
        return None

    return _get_user_from_token(token, db)


def is_admin(user: models.User | None) -> bool:
    return bool(user is not None and user.is_active and user.role == "admin")


def get_current_admin(
    user: models.User = Depends(get_current_user),
) -> models.User:
    if not is_admin(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền quản trị.",
        )

    return user
