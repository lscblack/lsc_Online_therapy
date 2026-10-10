"""Chat orchestration: triage -> (crisis? escalate) -> retrieve -> prompt -> generate -> guard -> persist.

Streaming approach (safety over latency): `stream()` runs the SAME full pipeline as `respond()`
(generation is buffered, guard applied, result persisted) and only THEN emits the final, guarded
answer in small chunks. No raw model token is ever sent to the client, so an ungrounded/sensitive/
unsafe answer can never be streamed; crisis turns never touch the model at all.
"""
import re
import uuid
from collections.abc import AsyncIterator
from dataclasses import asdict, dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.i18n import normalize_language, t
from app.models import User
from app.providers.factory import get_llm
from app.rag.prompt import assemble
from app.rag.retrieval import RetrievalResult, retrieve
from app.repositories.conversations import ConversationRepository
from app.safety import guard
from app.safety.referrals import lookup
from app.safety.triage import Category, Triage, classify, referral_category_for
from app.services.profile import ProfileService

HISTORY_LIMIT = 10
_CRISIS_COPY = {Category.crisis_self_harm: "crisis_self_harm",
                Category.gbv_sexual_violence: "crisis_gbv",
                Category.medical_emergency: "crisis_medical"}
_CITE = re.compile(r"\[S(\d+)\]")


class ConversationNotFound(Exception):
    pass


@dataclass
class ChatResult:
    answer: str
    citations: list[dict[str, Any]]
    conversation_id: uuid.UUID
    safety_flags: dict[str, Any]
    language: str
    # safety_flags keys: crisis, category, in_scope, needs_referral, in_knowledge, guard_reason, flags

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["conversation_id"] = str(self.conversation_id)
        return d


@dataclass
class _Outcome:
    answer: str
    citations: list[dict[str, Any]] = field(default_factory=list)
    flags: dict[str, Any] = field(default_factory=dict)


def _citations(answer: str, retrieval: RetrievalResult) -> list[dict[str, Any]]:
    seen: list[int] = []
    for m in _CITE.findall(answer):
        i = int(m)
        if 1 <= i <= len(retrieval.chunks) and i not in seen:
            seen.append(i)
    out = []
    for i in seen:
        c = retrieval.chunks[i - 1]
        out.append({"id": f"S{i}", "document_id": str(c.document_id), "title": c.title,
                    "chunk_id": str(c.chunk_id) if c.chunk_id else None,
                    "page": (c.meta or {}).get("page"), "score": round(c.score, 4)})
    return out


def _chunks(text: str, size: int = 6):
    """Whitespace-preserving word groups for SSE emission."""
    parts = re.findall(r"\S+\s*", text)
    for i in range(0, len(parts), size):
        yield "".join(parts[i:i + size])


class ChatService:
    def __init__(self, session: AsyncSession, llm=None) -> None:
        self.session = session
        self.llm = llm or get_llm()
        self.repo = ConversationRepository(session)

    async def _generate(self, messages: list[dict]) -> str:
        return "".join([c async for c in self.llm.stream_chat(messages)]).strip()

    async def _crisis(self, triage: Triage, lang: str) -> _Outcome:
        copy = t(_CRISIS_COPY.get(Category(triage.category), "crisis_self_harm"), lang)
        refs = await lookup(self.session, referral_category_for(triage.category))
        answer = guard.ensure_referral(copy, triage, refs, language=lang, force=True)
        return _Outcome(answer, [], {"crisis": True, "needs_referral": True, "in_knowledge": None})

    async def _normal(self, user: User, message: str, history: list[dict], triage: Triage,
                      lang: str) -> _Outcome:
        if not triage.in_scope:
            return _Outcome(t("out_of_scope", lang), [],
                            {"crisis": False, "needs_referral": False, "in_knowledge": None,
                             "guard_reason": "out_of_scope"})
        retrieval = await retrieve(self.session, message, lang)
        profile = await ProfileService(self.session).get(user)
        raw = await self._generate(assemble(message, retrieval, history, profile, lang))
        g = guard.ground(raw, retrieval, language=lang, category=triage)
        answer = g.answer
        sensitive = guard.is_sensitive(triage)
        if g.needs_referral or sensitive:
            refs = await lookup(self.session, referral_category_for(triage.category))
            answer = guard.ensure_referral(answer, triage, refs, language=lang,
                                           force=g.needs_referral)
        return _Outcome(answer, _citations(g.answer, retrieval) if g.allowed else [],
                        {"crisis": False, "needs_referral": g.needs_referral or sensitive,
                         "in_knowledge": retrieval.in_knowledge, "guard_reason": g.reason})

    async def respond(self, user: User, message: str, conversation_id: uuid.UUID | None = None,
                      language: str | None = None) -> ChatResult:
        conv = None
        if conversation_id is not None:
            conv = await self.repo.get_conversation(conversation_id, user)
            if conv is None:
                raise ConversationNotFound(str(conversation_id))
        lang = normalize_language(language or (conv.language if conv else None))
        history = await self.repo.get_history(conv.id, HISTORY_LIMIT) if conv else []

        triage = await classify(message, lang, llm=self.llm)
        out = (await self._crisis(triage, lang) if triage.is_crisis
               else await self._normal(user, message, history, triage, lang))
        flags = {**out.flags, "category": str(triage.category), "in_scope": triage.in_scope,
                 "flags": sorted(triage.flags), "triage_source": triage.source}

        if conv is None:
            conv = await self.repo.create_conversation(user, "text", lang)
        await self.repo.add_message(conv.id, "user", message, [], {})
        await self.repo.add_message(conv.id, "assistant", out.answer, out.citations, flags)
        await self.session.commit()
        return ChatResult(out.answer, out.citations, conv.id, flags, lang)

    async def stream(self, user: User, message: str, conversation_id: uuid.UUID | None = None,
                     language: str | None = None) -> AsyncIterator[dict[str, Any]]:
        """Yields {"event": "delta", "data": text} chunks of the GUARDED answer, then one
        {"event": "done", "data": ChatResult.to_dict()}. See module docstring."""
        result = await self.respond(user, message, conversation_id, language)
        for piece in _chunks(result.answer):
            yield {"event": "delta", "data": piece}
        yield {"event": "done", "data": result.to_dict()}
