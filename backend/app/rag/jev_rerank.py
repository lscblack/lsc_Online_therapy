"""Jev-powered passage filtering + re-ranking over a pgvector RetrievalResult.

Given the chunks pgvector returned (by cosine similarity), ask Jev per chunk whether it is
relevant, contains answer evidence, and/or is a prompt-injection attempt, then:
  * DROP injected or clearly-irrelevant chunks (they never reach the generator), and
  * RE-ORDER the survivors by relevance.

This tightens "grounded answers only": the generator sees fewer, better, non-malicious
sources. It fails SOFT — if Jev is off or unavailable the original RetrievalResult is
returned unchanged. `in_knowledge` is recomputed: if filtering removes everything, the turn
degrades to a safe referral exactly as an out-of-knowledge turn would.
"""
from __future__ import annotations

import logging

from app.core.config import get_settings
from app.providers.jev import get_jev
from app.rag.retrieval import RetrievalResult

logger = logging.getLogger(__name__)


async def rerank(query: str, retrieval: RetrievalResult) -> RetrievalResult:
    client = get_jev()
    if not client.rerank_enabled or not retrieval.chunks:
        return retrieval
    passages = [(c.title, c.content) for c in retrieval.chunks]
    try:
        accepted = await client.filter_passages(query, passages)
    except Exception as exc:  # noqa: BLE001 - never break retrieval
        logger.warning("Jev rerank failed (%s); keeping pgvector order", type(exc).__name__)
        return retrieval
    if accepted is None:  # Jev unavailable -> keep pgvector result untouched
        return retrieval

    kept = [retrieval.chunks[i] for i, _ in accepted]
    dropped = len(retrieval.chunks) - len(kept)
    if dropped:
        logger.info("Jev rerank: kept %d/%d passages (dropped %d)",
                    len(kept), len(retrieval.chunks), dropped)
    if not kept:
        # Everything was irrelevant/injected: treat as out of knowledge (safe referral).
        return RetrievalResult(chunks=[], max_score=0.0, in_knowledge=False)
    max_score = max((c.score for c in kept), default=0.0)
    return RetrievalResult(chunks=kept, max_score=max_score,
                           in_knowledge=max_score >= get_settings().retrieval_min_score)
