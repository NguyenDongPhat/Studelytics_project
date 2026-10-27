import os
from pathlib import Path

from dotenv import load_dotenv

# Xác định thư mục gốc backend
BACKEND_DIR = Path(__file__).resolve().parents[2]

# Nạp biến môi trường từ backend/.env
load_dotenv(BACKEND_DIR / ".env")


# =========================
# PostgreSQL
# =========================
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "Chưa cấu hình DATABASE_URL trong file backend/.env"
    )


# =========================
# Frontend và CORS
# =========================
FRONTEND_URL = os.getenv(
    "FRONTEND_URL",
    "http://localhost:5173",
).rstrip("/")

ALLOWED_ORIGINS = [
    origin.strip().rstrip("/")
    for origin in os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]


# =========================
# Upload PDF
# =========================
UPLOAD_DIR_VALUE = os.getenv("UPLOAD_DIR", "data/uploads")

UPLOAD_DIR = str(
    Path(UPLOAD_DIR_VALUE)
    if Path(UPLOAD_DIR_VALUE).is_absolute()
    else BACKEND_DIR / UPLOAD_DIR_VALUE
)


# =========================
# JWT authentication
# =========================
JWT_SECRET_KEY = (
    os.getenv("JWT_SECRET_KEY")
    or os.getenv("SECRET_KEY")
)

if not JWT_SECRET_KEY:
    raise RuntimeError(
        "Thiếu JWT_SECRET_KEY trong file backend/.env"
    )

JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440")
)

# Tương thích với một số module cũ còn dùng tên SECRET_KEY/ALGORITHM
SECRET_KEY = JWT_SECRET_KEY
ALGORITHM = JWT_ALGORITHM


# =========================
# Cookie authentication
# =========================
COOKIE_SECURE = (
    os.getenv("COOKIE_SECURE", "false").strip().lower()
    in {"1", "true", "yes", "on"}
)