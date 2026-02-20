from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.config import settings


@dataclass
class Chunk:
    idx: int
    text: str


def _normalize(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", (text or "").strip())


def chunk_markdown(md: str) -> list[Chunk]:
    """Chunk markdown into ~settings.LORE_CHUNK_TARGET_CHARS pieces.

    Heuristic: split on headings first, then fold into target sized windows with overlap.
    """
    md = _normalize(md)
    if not md:
        return []

    # Split on headings while keeping them
    parts = re.split(r"(?m)^(#{1,6}\s+.*)$", md)
    sections: list[str] = []
    buf = ""
    for p in parts:
        if not p:
            continue
        if p.lstrip().startswith("#") and "\n" not in p.strip():
            if buf.strip():
                sections.append(buf.strip())
            buf = p.strip() + "\n"
        else:
            buf += p
    if buf.strip():
        sections.append(buf.strip())

    target = int(settings.LORE_CHUNK_TARGET_CHARS)
    overlap = int(settings.LORE_CHUNK_OVERLAP_CHARS)

    chunks: list[Chunk] = []
    idx = 0
    for sec in sections:
        sec = sec.strip()
        if len(sec) <= target:
            chunks.append(Chunk(idx=idx, text=sec))
            idx += 1
            continue

        # Sliding window
        start = 0
        while start < len(sec):
            end = min(len(sec), start + target)
            window = sec[start:end].strip()
            if window:
                chunks.append(Chunk(idx=idx, text=window))
                idx += 1
            if end >= len(sec):
                break
            start = max(0, end - overlap)

    return chunks
