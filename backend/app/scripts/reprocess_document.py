"""Retry indexing an existing failed document, e.g. python scripts/reprocess_document.py 3."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app import models  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.rag.ingestion import process_and_save_pdf  # noqa: E402


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if len(sys.argv) != 2:
        print("Cách dùng: python scripts/reprocess_document.py <document_id>")
        return 2

    try:
        document_id = int(sys.argv[1])
    except ValueError:
        print("document_id phải là số nguyên.")
        return 2

    db = SessionLocal()
    try:
        doc = db.query(models.Document).filter(models.Document.id == document_id).first()
        if doc is None:
            print(f"Không tìm thấy tài liệu id={document_id} trong PostgreSQL.")
            return 1

        file_path = Path(doc.file_path)
        if not file_path.is_absolute():
            file_path = BACKEND_DIR / file_path
        if not file_path.is_file():
            print(f"Không tìm thấy file PDF đã lưu: {file_path}")
            print("Kiểm tra documents.file_path trong PostgreSQL trước khi chạy lại.")
            return 1

        print(f"Đang xử lý lại document_id={doc.id}, title={doc.title!r}")
        print(f"PDF: {file_path}")
        count = process_and_save_pdf(
            file_path=str(file_path),
            document_id=str(doc.id),
            owner_id=str(doc.owner_id),
            visibility=doc.visibility,
            document_title=doc.title,
            db=db,
        )
        print(f"Hoàn tất: {count} chunks. Kiểm tra documents.status='ready'.")
        return 0
    except Exception:
        logging.getLogger(__name__).exception("Reprocess thất bại cho document_id=%s", document_id)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
