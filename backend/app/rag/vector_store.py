from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

from app.rag.clients import get_embeddings
from app.rag.progress import set_progress
from app.rag.settings import CHROMA_PATH

COLLECTION_NAME = "studelytics_documents"


def _say(message: str) -> None:
    print(f"[Studelytics] {message}", flush=True)


def get_chroma_db():
    try:
        chroma_module = importlib.import_module("langchain_chroma")
        Chroma = chroma_module.Chroma
    except (ImportError, AttributeError) as exc:
        raise RuntimeError(
            "Thiếu langchain-chroma hoặc chromadb. Chạy: "
            "python -m pip install -U langchain-chroma chromadb"
        ) from exc

    path = Path(CHROMA_PATH)
    path.mkdir(parents=True, exist_ok=True)

    _say(f"Đang mở ChromaDB: path={path}, collection={COLLECTION_NAME}")

    db = Chroma(
        persist_directory=str(path),
        embedding_function=get_embeddings(),
        collection_name=COLLECTION_NAME,
    )

    _say(f"ChromaDB sẵn sàng: {path} / {COLLECTION_NAME}")
    return db


def add_chunks_to_chroma(
    chunks: list[Any],
    chroma_ids: list[str],
    document_id: str | int | None = None,
    batch_size: int = 8,
) -> int:
    if not chunks:
        _say(f"document_id={document_id}: không có chunks để embedding.")
        return 0

    if len(chunks) != len(chroma_ids):
        raise ValueError("Số chunk và chroma_id không khớp.")

    if batch_size < 1:
        raise ValueError("batch_size phải >= 1.")

    total_chunks = len(chunks)
    total_batches = (total_chunks + batch_size - 1) // batch_size
    progress_id = str(document_id) if document_id is not None else "unknown"

    _say(
        f"Bắt đầu embedding: document_id={document_id}, "
        f"tổng={total_chunks} chunks, batch_size={batch_size}, "
        f"số_batch={total_batches}."
    )

    set_progress(
        progress_id,
        progress=22,
        stage="embedding",
        message=f"Chuẩn bị embedding {total_chunks} chunks...",
        total_chunks=total_chunks,
        processed_chunks=0,
    )

    _say(
        f"Đang khởi tạo embedding model và ChromaDB "
        f"cho document_id={document_id}..."
    )

    db = get_chroma_db()
    processed_chunks = 0

    for batch_index, start in enumerate(
        range(0, total_chunks, batch_size),
        start=1,
    ):
        end = min(start + batch_size, total_chunks)
        batch_documents = chunks[start:end]
        batch_ids = chroma_ids[start:end]

        _say(
            f"Embedding batch {batch_index}/{total_batches} bắt đầu: "
            f"document_id={document_id}, "
            f"chunks {start + 1}-{end}/{total_chunks}."
        )

        db.add_documents(
            documents=batch_documents,
            ids=batch_ids,
        )

        processed_chunks = end
        percent = 22 + int(
            (processed_chunks / total_chunks) * 70
        )

        set_progress(
            progress_id,
            progress=min(percent, 92),
            stage="embedding",
            message=(
                f"Đã embedding và lưu vector: "
                f"{processed_chunks}/{total_chunks} chunks"
            ),
            total_chunks=total_chunks,
            processed_chunks=processed_chunks,
        )

        _say(
            f"Embedding batch {batch_index}/{total_batches} hoàn tất: "
            f"document_id={document_id}, "
            f"{processed_chunks}/{total_chunks} chunks "
            f"({int(processed_chunks / total_chunks * 100)}%)."
        )

    _say(
        f"Embedding hoàn tất: document_id={document_id}, "
        f"{processed_chunks}/{total_chunks} chunks."
    )

    return processed_chunks


def _get_raw_collection():
    try:
        chromadb_module = importlib.import_module("chromadb")
        PersistentClient = chromadb_module.PersistentClient
    except (ImportError, AttributeError) as exc:
        raise RuntimeError(
            "Thiếu chromadb. Chạy: "
            "python -m pip install -U chromadb"
        ) from exc

    path = Path(CHROMA_PATH)
    path.mkdir(parents=True, exist_ok=True)

    client = PersistentClient(path=str(path))

    return client.get_or_create_collection(
        name=COLLECTION_NAME
    )


def update_document_visibility_in_chroma(
    document_id: str,
    visibility: str,
) -> int:
    if visibility not in {"private", "shared", "public"}:
        raise ValueError(
            "visibility phải là private, shared hoặc public."
        )

    path = Path(CHROMA_PATH)

    if not path.exists():
        return 0

    collection = _get_raw_collection()

    result = collection.get(
        where={"document_id": str(document_id)},
        include=["metadatas"],
    )

    ids = result.get("ids", []) if result else []
    metadatas = result.get("metadatas", []) if result else []

    if not ids:
        return 0

    updated_metadatas = []

    for metadata in metadatas:
        item = dict(metadata or {})
        item["visibility"] = visibility
        updated_metadatas.append(item)

    collection.update(
        ids=ids,
        metadatas=updated_metadatas,
    )

    _say(
        f"Đã cập nhật visibility={visibility} "
        f"cho document_id={document_id}: {len(ids)} vectors."
    )

    return len(ids)


def delete_document_from_chroma(
    document_id: str,
) -> int:
    path = Path(CHROMA_PATH)

    if not path.exists():
        return 0

    collection = _get_raw_collection()

    result = collection.get(
        where={"document_id": str(document_id)},
        include=["metadatas"],
    )

    ids = result.get("ids", []) if result else []

    if ids:
        collection.delete(ids=ids)

    _say(
        f"Dọn vector cũ document_id={document_id}: "
        f"{len(ids)} vectors."
    )

    return len(ids)