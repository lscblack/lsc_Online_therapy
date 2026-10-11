"""Recursive, paragraph-aware chunking.

Token counting is approximate and dependency-free: tokens = ceil(words * 1.3), where
words are whitespace-separated. Splitting order: paragraphs (blank line) -> sentences ->
words. Every chunk satisfies count_tokens(content) <= max_tokens. Overlap: each chunk
(after the first) is prefixed with the trailing words of the previous chunk, up to
`overlap * max_tokens` tokens, dropped when it would not fit.
"""
import math
import re
from dataclasses import dataclass, field

from app.rag.extract import Page

TOKENS_PER_WORD = 1.3
_SENT = re.compile(r"(?<=[.!?])\s+")
_PARA = re.compile(r"\n\s*\n")


def count_tokens(text: str) -> int:
    return math.ceil(len(text.split()) * TOKENS_PER_WORD)


@dataclass(frozen=True)
class Chunk:
    index: int
    content: str
    token_count: int
    meta: dict = field(default_factory=dict)


def _is_heading(para: str) -> bool:
    return "\n" not in para and len(para.split()) <= 8 and para[-1] not in ".!?:;,"


def _split_words(text: str, max_words: int) -> list[str]:
    w = text.split()
    return [" ".join(w[i:i + max_words]) for i in range(0, len(w), max_words)]


def _segments(pages: list[Page], max_words: int) -> list[tuple[str, int, str | None]]:
    segs: list[tuple[str, int, str | None]] = []
    section: str | None = None
    for page in pages:
        for para in _PARA.split(page.text):
            para = " ".join(para.split())  # normalize whitespace
            if not para:
                continue
            if _is_heading(para):
                section = para
            pieces = [para]
            if len(para.split()) > max_words:
                pieces = [s for s in _SENT.split(para) if s]
            for piece in pieces:
                for part in _split_words(piece, max_words):
                    segs.append((part, page.page_number, section))
    return segs


def chunk(pages: list[Page], max_tokens: int = 500, overlap: float = 0.15) -> list[Chunk]:
    max_words = max(1, int(max_tokens / TOKENS_PER_WORD))
    while math.ceil(max_words * TOKENS_PER_WORD) > max_tokens and max_words > 1:
        max_words -= 1  # float-safety: guarantee the bound
    overlap_words = int(max_words * max(0.0, min(overlap, 0.5)))
    segs = _segments(pages, max_words)

    chunks: list[Chunk] = []
    cur: list[str] = []
    cur_words = 0
    first_page = first_section = None
    tail: list[str] = []

    def flush() -> None:
        nonlocal cur, cur_words, tail
        if not cur:
            return
        body = "\n\n".join(cur)
        content = (" ".join(tail) + "\n\n" + body) if tail else body
        meta = {"page": first_page}
        if first_section:
            meta["section"] = first_section
        chunks.append(Chunk(len(chunks), content, count_tokens(content), meta))
        words = content.split()
        tail = words[-overlap_words:] if overlap_words else []
        cur, cur_words = [], 0

    for text, page, section in segs:
        n = len(text.split())
        if cur and len(tail) + cur_words + n > max_words:
            flush()
        if not cur:
            first_page, first_section = page, section
            if len(tail) + n > max_words:
                tail = []
        cur.append(text)
        cur_words += n
    flush()
    return chunks
