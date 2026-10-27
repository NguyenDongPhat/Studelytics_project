from __future__ import annotations


def split_pages(pages, chunk_size: int = 600, chunk_overlap: int = 100):
    if chunk_size <= 0:
        raise ValueError("chunk_size phải lớn hơn 0.")
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap phải >= 0 và nhỏ hơn chunk_size.")

    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter
    except ImportError as exc:
        raise RuntimeError(
            "Thiếu thư viện langchain-text-splitters. Cài requirements-rag.txt."
        ) from exc

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        add_start_index=True,
    )
    chunks = splitter.split_documents(pages)

    for chunk in chunks:
        metadata = dict(getattr(chunk, "metadata", {}) or {})
        if "page_number" not in metadata:
            try:
                metadata["page_number"] = int(metadata.get("page", 0)) + 1
            except (TypeError, ValueError):
                metadata["page_number"] = 1
        chunk.metadata = metadata

    return chunks
