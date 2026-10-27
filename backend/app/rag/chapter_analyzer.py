
from __future__ import annotations

import re

_HEADING_PATTERNS = (
    re.compile(r"^\s*(?:chương|chapter)\s+([0-9]+|[ivxlcdm]+)\s*[:.\-–—]?\s*(.*?)\s*$", re.I),
    re.compile(r"^\s*([0-9]{1,2}(?:\.[0-9]{1,2})?)\s*[.)\-:]\s+(.{3,120})\s*$"),
)


def detect_chapter_candidates(pages) -> list[dict]:
    candidates: list[dict] = []
    seen: set[tuple[int, str]] = set()

    for page in pages:
        page_number = page.metadata.get("page_number", int(page.metadata.get("page", 0)) + 1)
        text = getattr(page, "page_content", "") or ""
        for line in text.splitlines():
            line = " ".join(line.strip().split())
            if not line or len(line) > 160:
                continue
            for pattern in _HEADING_PATTERNS:
                match = pattern.match(line)
                if not match:
                    continue
                if pattern is _HEADING_PATTERNS[0]:
                    number_token, title = match.group(1), match.group(2)
                    try:
                        chapter_number = int(number_token)
                    except ValueError:
                        chapter_number = len(candidates) + 1
                    title = title.strip(" .:-–—") or f"Chương {number_token}"
                else:
                    number_token, title = match.group(1), match.group(2)
                    chapter_number = len(candidates) + 1
                    title = f"{number_token}. {title.strip()}"
                key = (int(page_number), title.casefold())
                if key not in seen:
                    candidates.append({
                        "chapter_number": max(1, chapter_number),
                        "title": title[:500],
                        "start_page": int(page_number),
                    })
                    seen.add(key)
                break

    for ordinal, item in enumerate(candidates, start=1):
        item["chapter_number"] = ordinal

    return candidates
