from __future__ import annotations

import os
from functools import lru_cache

from app.rag.settings import GROQ_API_KEY, GROQ_MODEL, HF_EMBEDDING_MODEL, HF_TOKEN

EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "local").strip().lower()
EMBEDDING_DEVICE = os.getenv("EMBEDDING_DEVICE", "cpu").strip().lower()


@lru_cache(maxsize=1)
def get_embeddings():
    """Load embeddings locally by default, avoiding paid HF Inference API calls.

    Set EMBEDDING_PROVIDER=endpoint only if you intentionally want to use
    Hugging Face's hosted Inference API and have available credits.
    """
    if EMBEDDING_PROVIDER in {"local", "sentence-transformers", "huggingface-local"}:
        try:
            from langchain_huggingface import HuggingFaceEmbeddings
        except ImportError as exc:
            raise RuntimeError(
                "Thiếu thư viện embedding local. Chạy: "
                'python -m pip install -U langchain-chroma "langchain-huggingface[full]"'
            ) from exc

        model_name = HF_EMBEDDING_MODEL or "sentence-transformers/all-MiniLM-L6-v2"
        print(
            f"[Studelytics] Đang nạp embedding local: {model_name} "
            f"(device={EMBEDDING_DEVICE})",
            flush=True,
        )
        return HuggingFaceEmbeddings(
            model_name=model_name,
            model_kwargs={"device": EMBEDDING_DEVICE},
            encode_kwargs={"normalize_embeddings": True},
        )

    if EMBEDDING_PROVIDER in {"endpoint", "huggingface-endpoint", "api"}:
        if not HF_TOKEN:
            raise RuntimeError(
                "EMBEDDING_PROVIDER=endpoint yêu cầu HF_TOKEN và credits Hugging Face còn hoạt động."
            )
        try:
            from langchain_huggingface import HuggingFaceEndpointEmbeddings
        except ImportError as exc:
            raise RuntimeError(
                "Thiếu langchain-huggingface. Chạy: python -m pip install -U langchain-huggingface"
            ) from exc
        return HuggingFaceEndpointEmbeddings(
            model=HF_EMBEDDING_MODEL,
            huggingfacehub_api_token=HF_TOKEN,
        )

    raise RuntimeError(
        f"EMBEDDING_PROVIDER không hợp lệ: {EMBEDDING_PROVIDER!r}. "
        "Dùng 'local' hoặc 'endpoint'."
    )


@lru_cache(maxsize=1)
def get_llm():
    """Create the Groq chat model only when a generation task is requested."""
    if not GROQ_API_KEY:
        raise RuntimeError("Thiếu GROQ_API_KEY trong backend/.env để dùng AI.")

    try:
        from langchain_groq import ChatGroq
    except ImportError as exc:
        raise RuntimeError(
            "Thiếu thư viện langchain-groq. Cài requirements RAG của dự án."
        ) from exc

    return ChatGroq(
        model=GROQ_MODEL,
        api_key=GROQ_API_KEY,
        temperature=0.2,
    )
