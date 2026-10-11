"""Read-only pgvector cosine retrieval over approved+indexed chunks.

Score convention: score = 1 - cosine_distance (higher = better, 1.0 identical).
in_knowledge = max_score >= settings.retrieval_min_score (default 0.3, tunable via
RETRIEVAL_MIN_SCORE; calibrate against the real e5 model on the approved corpus).
"""
import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.i18n import recognised_language
from app.models.document import Document, DocumentChunk
from app.providers.base import EmbeddingProvider
from app.providers.factory import get_embeddings
from app.repositories.documents import DocumentRepository


@dataclass
class RetrievedChunk:
    content: str
    document_id: uuid.UUID
    title: str
    score: float
    meta: dict[str, Any] = field(default_factory=dict)
    chunk_id: uuid.UUID | None = None


@dataclass
class RetrievalResult:
    chunks: list[RetrievedChunk]
    max_score: float
    in_knowledge: bool


async def _search(session: AsyncSession, qvec: list[float], k: int, language: str | None):
    dist = DocumentChunk.embedding.cosine_distance(qvec).label("distance")
    stmt = DocumentRepository.approved_chunks_stmt().add_columns(Document.title, dist)
    if language:
        stmt = stmt.where(or_(DocumentChunk.language == language,
                              DocumentChunk.language.is_(None)))
    stmt = stmt.order_by(dist, DocumentChunk.id).limit(k)
    return (await session.execute(stmt)).all()


async def retrieve(session: AsyncSession, query: str, language: str | None = None,
                   k: int = 6, embeddings: EmbeddingProvider | None = None) -> RetrievalResult:
    provider = embeddings or get_embeddings()
    qvec = (await provider.embed([query], "query"))[0]
    # Only filter for a recognised language; anything else (mixed/unknown) searches all.
    lang = recognised_language(language)
    rows = await _search(session, qvec, k, lang) if lang else []
    if not rows:
        rows = await _search(session, qvec, k, None)  # fall back to all approved
    chunks = [RetrievedChunk(content=c.content, document_id=c.document_id, title=title,
                             score=float(1.0 - d), meta=dict(c.meta or {}), chunk_id=c.id)
              for c, title, d in rows]
    max_score = max((c.score for c in chunks), default=0.0)
    return RetrievalResult(chunks=chunks, max_score=max_score,
                           in_knowledge=max_score >= get_settings().retrieval_min_score)
