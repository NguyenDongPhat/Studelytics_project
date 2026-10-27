from __future__ import annotations

from threading import Lock
from time import time
from typing import Any

_lock = Lock()
_progress: dict[str, dict[str, Any]] = {}


def set_progress(
    document_id: str | int,
    *,
    progress: int,
    stage: str,
    message: str,
    status: str = "processing",
    total_chunks: int | None = None,
    processed_chunks: int | None = None,
) -> None:
    item: dict[str, Any] = {
        "progress": max(0, min(100, int(progress))),
        "stage": str(stage),
        "message": str(message),
        "status": str(status),
        "updated_at": time(),
    }
    if total_chunks is not None:
        item["total_chunks"] = int(total_chunks)
    if processed_chunks is not None:
        item["processed_chunks"] = int(processed_chunks)
    with _lock:
        _progress[str(document_id)] = item


def get_progress(document_id: str | int) -> dict[str, Any] | None:
    with _lock:
        item = _progress.get(str(document_id))
        return dict(item) if item is not None else None


def clear_progress(document_id: str | int) -> None:
    with _lock:
        _progress.pop(str(document_id), None)
