from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from app import models
from app.database import SessionLocal
from app.rag.chunking import split_pages
from app.rag.pdf_parser import load_pdf_pages
from app.rag.progress import set_progress
from app.rag.vector_store import add_chunks_to_chroma, delete_document_from_chroma

logger = logging.getLogger(__name__)


def _progress(document_id: int, progress: int, stage: str, message: str,
              total_chunks: int | None = None, processed_chunks: int | None = None,
              status: str = "processing") -> None:
    set_progress(
        str(document_id),
        progress=progress,
        stage=stage,
        message=message,
        status=status,
        total_chunks=total_chunks,
        processed_chunks=processed_chunks,
    )
    print(f"[Studelytics][document_id={document_id}][{progress}%][{stage}] {message}", flush=True)


def process_and_save_pdf(
    file_path: str,
    document_id: str | int,
    owner_id: str | int,
    visibility: str,
    document_title: str | None = None,
    db=None,
) -> int:
    owned_session = db is None
    session = db or SessionLocal()
    doc_id = int(document_id)

    try:
        document = session.query(models.Document).filter(models.Document.id == doc_id).first()
        if document is None:
            raise ValueError(f"Không tìm thấy tài liệu id={doc_id} trong PostgreSQL.")

        document.status = "processing"
        session.commit()
        _progress(doc_id, 5, "parsing", f"Bắt đầu đọc PDF: {file_path}")

        pages = load_pdf_pages(file_path)
        text_page_count = sum(
            1 for page in pages if (getattr(page, "page_content", "") or "").strip()
        )
        if text_page_count == 0:
            raise ValueError(
                "PDF không trích xuất được văn bản. Nếu đây là PDF scan, cần bổ sung OCR."
            )

        document.total_pages = len(pages)
        session.commit()
        _progress(
            doc_id, 15, "parsing",
            f"Đọc được {len(pages)} trang; {text_page_count} trang có văn bản."
        )

        _progress(doc_id, 18, "chunking", "Đang chia nội dung thành chunks...")
        chunks = split_pages(pages, chunk_size=600, chunk_overlap=100)
        if not chunks:
            raise ValueError("Không tạo được chunks từ nội dung PDF.")

        title = document_title or document.title or Path(file_path).name
        valid_visibility = visibility if visibility in {"private", "shared", "public"} else document.visibility
        chroma_ids: list[str] = []
        chunk_rows: list[Any] = []

        for index, chunk in enumerate(chunks):
            metadata = dict(chunk.metadata or {})
            try:
                page_number = int(metadata.get("page_number", metadata.get("page", 0) + 1))
                if page_number < 1:
                    page_number = 1
            except (TypeError, ValueError):
                page_number = 1

            content = (getattr(chunk, "page_content", "") or "").strip()
            if not content:
                continue

            chroma_id = f"studelytics-doc-{doc_id}-chunk-{index}"
            chroma_ids.append(chroma_id)
            chunk.metadata.update({
                "document_id": str(doc_id),
                "document_title": str(title),
                "owner_id": str(owner_id),
                "visibility": valid_visibility,
                "page_number": page_number,
                "chunk_index": index,
                "chroma_id": chroma_id,
            })
            chunk_rows.append(models.DocumentChunk(
                document_id=doc_id,
                chapter_id=None,
                page_number=page_number,
                chunk_index=index,
                chroma_id=chroma_id,
                content=content,
            ))

        if not chunk_rows:
            raise ValueError("Toàn bộ chunks đều rỗng sau khi chuẩn hóa văn bản.")

        _progress(
            doc_id, 20, "chunking",
            f"Đã chia {len(pages)} trang thành {len(chunk_rows)} chunks.",
            total_chunks=len(chunk_rows), processed_chunks=0,
        )

        # Remove the previous index and relational chunks before reprocessing this document.
        delete_document_from_chroma(str(doc_id))
        session.query(models.DocumentChunk).filter(
            models.DocumentChunk.document_id == doc_id
        ).delete(synchronize_session=False)
        session.add_all(chunk_rows)
        document.total_pages = len(pages)
        document.visibility = valid_visibility
        session.flush()
        session.commit()
        _progress(
            doc_id, 21, "database",
            f"Đã lưu {len(chunk_rows)} chunks và nội dung vào PostgreSQL; bắt đầu embedding.",
            total_chunks=len(chunk_rows), processed_chunks=0,
        )

        saved = add_chunks_to_chroma(
            chunks=[chunk for chunk in chunks if (getattr(chunk, "page_content", "") or "").strip()],
            chroma_ids=chroma_ids,
            document_id=str(doc_id),
        )
        if saved != len(chroma_ids):
            raise RuntimeError(
                f"Số chunks được lưu ChromaDB không khớp: {saved}/{len(chroma_ids)}."
            )

        document.status = "ready"
        session.commit()
        _progress(
            doc_id, 100, "completed",
            f"Hoàn tất: {len(pages)} trang, {len(chunk_rows)} chunks đã lưu PostgreSQL và ChromaDB.",
            total_chunks=len(chunk_rows), processed_chunks=len(chunk_rows), status="ready",
        )
        logger.info(
            "Studelytics indexed document_id=%s pages=%s chunks=%s",
            doc_id, len(pages), len(chunk_rows),
        )
        return len(chunk_rows)

    except Exception as exc:
        session.rollback()
        logger.exception("Studelytics PDF ingestion failed for document_id=%s", doc_id)
        try:
            delete_document_from_chroma(str(doc_id))
        except Exception:
            logger.exception("Could not clean up Chroma vectors for document %s", doc_id)
        try:
            document = session.query(models.Document).filter(models.Document.id == doc_id).first()
            if document is not None:
                document.status = "failed"
                session.commit()
        except Exception:
            session.rollback()
        _progress(doc_id, 100, "failed", str(exc), status="failed")
        raise
    finally:
        if owned_session:
            session.close()
