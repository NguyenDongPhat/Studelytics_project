import os
from contextlib import asynccontextmanager

from app.schemas import users
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app import models  # Đăng ký các ORM models
from app.core.config import ALLOWED_ORIGINS, UPLOAD_DIR
from app.database import engine
from app.routers import auth, documents, flashcards, search, social, users, chat, admin

@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    # Kiểm tra kết nối PostgreSQL
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))

    print("[Studelytics] PostgreSQL connected successfully.")
    print(f"[Studelytics] Allowed origins: {ALLOWED_ORIGINS}")

    yield

    engine.dispose()


app = FastAPI(
    title="Studelytics API",
    description="AI-powered intelligent learning assistant",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Hiện tại chỉ bật Auth đã chuyển sang Studelytics
app.include_router(auth.router),
app.include_router(users.router),
app.include_router(documents.router),
app.include_router(flashcards.router),
app.include_router(search.router),
app.include_router(social.router),
app.include_router(chat.router),
app.include_router(admin.router)


@app.get("/health", tags=["System"])
def health_check():
    return {
        "status": "ok",
        "application": "Studelytics",
    }


@app.get("/health/db", tags=["System"])
def database_health_check():
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))

    return {
        "status": "ok",
        "database": "PostgreSQL",
    }


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )