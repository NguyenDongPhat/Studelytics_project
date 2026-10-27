from __future__ import annotations

from pathlib import Path
from typing import Any


def load_pdf_pages(file_path: str | Path) -> list[Any]:
    path = Path(file_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Không tìm thấy file PDF: {path}")
    if path.suffix.lower() != ".pdf":
        raise ValueError("Chỉ hỗ trợ file PDF.")

    try:
        from langchain_community.document_loaders import PyPDFLoader
    except ImportError as exc:
        raise RuntimeError(
            "Thiếu langchain-community hoặc pypdf. Cài bằng: "
            "python -m pip install -U langchain-community pypdf"
        ) from exc

    pages = PyPDFLoader(str(path)).load()
    for index, page in enumerate(pages, start=1):
        metadata = dict(getattr(page, "metadata", {}) or {})
        raw_page = metadata.get("page")
        try:
            page_number = int(raw_page) + 1 if raw_page is not None else index
        except (TypeError, ValueError):
            page_number = index
        metadata["page_number"] = max(1, page_number)
        page.metadata = metadata

    if not pages:
        raise ValueError("PDF không có trang nào để đọc.")
    return pages


def load_document_text(file_path: str | Path, max_chars: int = 14000) -> str:
    if max_chars <= 0:
        return ""

    pages = load_pdf_pages(file_path)
    parts: list[str] = []
    remaining = max_chars

    for page in pages:
        page_text = (getattr(page, "page_content", "") or "").strip()
        if not page_text:
            continue
        page_number = page.metadata.get("page_number", 1)
        part = f"Trang {page_number}:\n{page_text}"
        if remaining <= 0:
            break
        part = part[:remaining]
        parts.append(part)
        remaining -= len(part)

    return "\n\n---\n\n".join(parts)[:max_chars]
