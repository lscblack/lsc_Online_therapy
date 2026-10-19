"""Chat orchestration: triage -> (crisis? escalate) -> retrieve -> prompt -> generate -> guard -> persist.

Streaming approach (safety over latency): `stream()` runs the SAME full pipeline as `respond()`
(generation is buffered, guard applied, result persisted) and only THEN emits the final, guarded
answer in small chunks. No raw model token is ever sent to the client, so an ungrounded/sensitive/
unsafe answer can never be streamed; crisis turns never touch the model at all.
"""
import logging
import re
import uuid
from collections.abc import AsyncIterator
from dataclasses import asdict, dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.i18n import normalize_language, t
from app.models import ConversationMode, User
from app.providers.factory import get_llm
from app.rag.prompt import assemble
from app.rag.jev_rerank import rerank as jev_rerank
from app.rag.retrieval import RetrievalResult, retrieve
from app.repositories.conversations import ConversationRepository
from app.providers.registry import ACTIVE_MODEL_KEY, ACTIVE_PROVIDER_KEY
from app.repositories.settings import SettingsRepository
from app.safety import guard
from app.safety.referrals import lookup
from app.safety.triage import Category, Triage, classify, referral_category_for
from app.services.profile import ProfileService

logger = logging.getLogger(__name__)
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
        self._llm = llm  # resolved lazily: voice transcribe/speak never need a working LLM
        self._injected_llm = llm  # the test-injected LLM, if any (used for triage too)
        self._provider: str | None = None  # admin-selected provider (DB) or env default
        self._model: str | None = None      # admin-selected model (DB) or env default
        self._triage: object | None = None
        self.repo = ConversationRepository(session)

    @property
    def llm(self):
        if self._llm is None:
            self._llm = (get_llm(model=self._model, provider=self._provider)
                         if self._provider else get_llm())
        return self._llm

    @property
    def triage_llm(self):
        """A FAST model for the triage classification, independent of the (possibly slow) active
        chat model — so picking a slow answer model doesn't slow down every message. Tests' injected
        LLM is used as-is."""
        if self._injected_llm is not None:
            return self._injected_llm
        if self._triage is None:
            from app.core.config import get_settings
            s = get_settings()
            try:
                self._triage = get_llm(provider=s.default_llm_provider, model=s.default_llm_model)
            except Exception:  # noqa: BLE001 - fall back to the active model if the default is unset
                self._triage = self.llm
        return self._triage

    async def _resolve_active_model(self) -> None:
        """Load the admin-selected provider/model (falling back to the env defaults) before the
        LLM is built. No-op when an LLM was injected (tests) or already built."""
        if self._llm is None and self._provider is None:
            from app.core.config import get_settings
            s = get_settings()
            try:
                repo = SettingsRepository(self.session)
                self._provider = await repo.get(ACTIVE_PROVIDER_KEY) or s.default_llm_provider
                self._model = await repo.get(ACTIVE_MODEL_KEY) or s.default_llm_model
            except Exception:  # noqa: BLE001 - fall back to env defaults if the lookup fails
                logger.debug("active-model lookup failed; using env default", exc_info=True)
                self._provider = s.default_llm_provider
                self._model = s.default_llm_model

    async def _generate(self, messages: list[dict]) -> str:
        try:
            return "".join([c async for c in self.llm.stream_chat(messages)]).strip()
        except Exception:
            # The admin-selected model failed (e.g. a broken free model). Fall back once to the
            # reliable env default so a bad model choice never silently breaks chat.
            from app.core.config import get_settings
            s = get_settings()
            if self._provider and (self._provider, self._model) != (
                    s.default_llm_provider, s.default_llm_model):
                logger.warning("active model %s/%s failed; falling back to %s/%s",
                               self._provider, self._model, s.default_llm_provider, s.default_llm_model)
                fb = get_llm(provider=s.default_llm_provider, model=s.default_llm_model)
                return "".join([c async for c in fb.stream_chat(messages)]).strip()
            raise

    async def _referrals(self, triage: Triage) -> list:
        try:
            return await lookup(self.session, referral_category_for(triage.category))
        except Exception as exc:  # noqa: BLE001 - a catalog failure must not remove the next step
            logger.warning("referral lookup failed (%s); using generic fallback", type(exc).__name__)
            await self.session.rollback()
            return []

    async def _degraded(self, triage: Triage, lang: str) -> _Outcome:
        refs = await self._referrals(triage)
        answer = guard.ensure_referral(t("disclaimer", lang), triage, refs, language=lang, force=True)
        return _Outcome(answer, [], {"crisis": False, "needs_referral": True, "in_knowledge": None,
                                     "guard_reason": "provider_error"})

    async def _crisis(self, triage: Triage, lang: str) -> _Outcome:
        copy = t(_CRISIS_COPY.get(Category(triage.category), "crisis_self_harm"), lang)
        refs = await self._referrals(triage)
        answer = guard.ensure_referral(copy, triage, refs, language=lang, force=True)
        return _Outcome(answer, [], {"crisis": True, "needs_referral": True, "in_knowledge": None})

    def _social_messages(self, history: list[dict], message: str, lang: str) -> list[dict]:
        system = "\n\n".join([t("persona", lang), t("style", lang),
                              t("language_directive", lang), t("social_directive", lang)])
        return [{"role": "system", "content": system},
                *[{"role": m["role"], "content": m["content"]} for m in history],
                {"role": "user", "content": message}]

    async def _social_fallback(self, user: User, lang: str) -> str:
        try:
            profile = await ProfileService(self.session).get(user)
            name = (profile.nickname or "").strip() or None if profile else None
        except Exception:  # noqa: BLE001
            name = None
        key = "greeting_reply_named" if name else "greeting_reply"
        return t(key, lang).format(name=name) if name else t(key, lang)

    async def _social(self, user: User, message: str, history: list[dict], lang: str) -> _Outcome:
        """A natural, human reply to a greeting / small-talk — generated by the LLM (varied), with
        no retrieval, no referral and no citations. Falls back to a canned greeting if the LLM fails."""
        try:
            answer = (await self._generate(self._social_messages(history, message, lang))).strip()
            if not answer:
                raise ValueError("empty social reply")
        except Exception:  # noqa: BLE001 - small talk must never error; use the canned greeting
            answer = await self._social_fallback(user, lang)
        return _Outcome(answer, [], {"crisis": False, "needs_referral": False,
                                     "in_knowledge": None, "guard_reason": "social"})

    def _offscope_messages(self, history: list[dict], message: str, lang: str) -> list[dict]:
        system = "\n\n".join([t("persona", lang), t("style", lang),
                              t("language_directive", lang), t("offscope_directive", lang)])
        return [{"role": "system", "content": system},
                *[{"role": m["role"], "content": m["content"]} for m in history],
                {"role": "user", "content": message}]

    async def _offscope(self, message: str, history: list[dict], lang: str) -> _Outcome:
        """A warm, personal decline for an off-topic question — acknowledges what was asked and
        redirects to health, generated by the LLM. Falls back to the canned line if the LLM fails."""
        try:
            answer = (await self._generate(self._offscope_messages(history, message, lang))).strip()
            if not answer:
                raise ValueError("empty off-scope reply")
        except Exception:  # noqa: BLE001
            answer = t("out_of_scope", lang)
        return _Outcome(answer, [], {"crisis": False, "needs_referral": False,
                                     "in_knowledge": None, "guard_reason": "out_of_scope"})

    async def _stream_tokens(self, messages: list[dict]) -> AsyncIterator[str]:
        """Yield tokens from the active LLM live. If the active model fails BEFORE any token,
        fall back once to the reliable default; a mid-stream failure is raised to the caller."""
        started = False
        try:
            async for tok in self.llm.stream_chat(messages):
                started = True
                yield tok
        except Exception:
            if started:
                raise
            from app.core.config import get_settings
            s = get_settings()
            if self._provider and (self._provider, self._model) != (
                    s.default_llm_provider, s.default_llm_model):
                fb = get_llm(provider=s.default_llm_provider, model=s.default_llm_model)
                async for tok in fb.stream_chat(messages):
                    yield tok
            else:
                raise

    @staticmethod
    def _build_flags(out: "_Outcome", triage: Triage) -> dict:
        f = {**out.flags, "category": str(triage.category), "in_scope": triage.in_scope,
             "flags": sorted(triage.flags), "triage_source": triage.source}
        if triage.confidence is not None:
            f["triage_confidence"] = round(triage.confidence, 3)
        if triage.low_confidence:
            f["low_confidence"] = True
        return f

    async def _persist(self, user: User, conv, message: str, out: "_Outcome", flags: dict,
                       lang: str, mode: ConversationMode = "text") -> ChatResult:
        best_effort = bool(flags.get("crisis")) or flags.get("guard_reason") == "provider_error"
        cid = conv.id if conv else None
        conv_id_known = cid
        try:
            if conv is None:
                conv = await self.repo.create_conversation(user, str(mode), lang)
                cid = conv.id
            await self.repo.add_message(conv.id, "user", message, [], {})
            await self.repo.add_message(conv.id, "assistant", out.answer, out.citations, flags)
            await self.session.commit()
        except Exception as exc:  # noqa: BLE001
            if not best_effort:
                raise
            logger.error("chat persistence failed (%s); returning answer unsaved", type(exc).__name__)
            await self.session.rollback()
            cid = conv_id_known if conv_id_known is not None else uuid.uuid4()
            flags["persisted"] = False
        return ChatResult(out.answer, out.citations, cid, flags, lang)

    async def _retrieve_ranked(self, message: str, lang: str) -> RetrievalResult:
        """pgvector retrieval, then (if Jev is configured) drop injected/irrelevant passages and
        re-rank by relevance. Pulls more candidates when Jev will filter them down."""
        from app.core.config import get_settings
        from app.providers.jev import get_jev
        s = get_settings()
        k = s.jev_rerank_candidates if get_jev().rerank_enabled else 6
        retrieval = await retrieve(self.session, message, lang, k=k)
        return await jev_rerank(message, retrieval)

    async def _normal(self, user: User, message: str, history: list[dict], triage: Triage,
                      lang: str) -> _Outcome:
        if not triage.in_scope:
            return await self._offscope(message, history, lang)
        try:
            retrieval = await self._retrieve_ranked(message, lang)
            profile = await ProfileService(self.session).get(user)
            raw = await self._generate(assemble(message, retrieval, history, profile, lang))
        except Exception as exc:  # noqa: BLE001 - provider/DB failure degrades to a safe referral
            logger.error("chat retrieval/generation failed (%s); degrading", type(exc).__name__)
            await self.session.rollback()
            return await self._degraded(triage, lang)
        g = guard.ground(raw, retrieval, language=lang, category=triage)
        answer = g.answer
        sensitive = guard.is_sensitive(triage) or triage.low_confidence
        if g.needs_referral or sensitive:
            refs = await self._referrals(triage)
            answer = guard.ensure_referral(answer, triage, refs, language=lang,
                                           force=g.needs_referral)
        return _Outcome(answer, _citations(g.answer, retrieval) if g.allowed else [],
                        {"crisis": False, "needs_referral": g.needs_referral or sensitive,
                         "in_knowledge": retrieval.in_knowledge, "guard_reason": g.reason})

    async def respond(self, user: User, message: str, conversation_id: uuid.UUID | None = None,
                      language: str | None = None, mode: ConversationMode = "text") -> ChatResult:
        if not message or not message.strip():
            raise ValueError("message must not be empty")
        message = message.strip()
        conv = None
        if conversation_id is not None:
            conv = await self.repo.get_conversation(conversation_id, user)
            if conv is None:
                raise ConversationNotFound(str(conversation_id))
        lang = normalize_language(language or (conv.language if conv else None))
        history = await self.repo.get_history(conv.id, HISTORY_LIMIT) if conv else []

        await self._resolve_active_model()
        triage = await classify(message, lang, llm=self.triage_llm)
        if triage.is_crisis:
            out = await self._crisis(triage, lang)
        elif triage.category == str(Category.social):
            out = await self._social(user, message, history, lang)
        else:
            out = await self._normal(user, message, history, triage, lang)
        flags = self._build_flags(out, triage)
        return await self._persist(user, conv, message, out, flags, lang, mode)

    async def stream(self, user: User, message: str, conversation_id: uuid.UUID | None = None,
                     language: str | None = None) -> AsyncIterator[dict[str, Any]]:
        """True token streaming: yields {"event":"delta","data":token} as the model produces them,
        a {"event":"replace","data":text} if the safety guard changes the streamed text, then one
        {"event":"done","data":ChatResult.to_dict()}. Crisis/out-of-scope/out-of-knowledge replies
        are short and canned, so they are emitted in chunks without a live model call."""
        if not message or not message.strip():
            raise ValueError("message must not be empty")
        message = message.strip()
        conv = None
        if conversation_id is not None:
            conv = await self.repo.get_conversation(conversation_id, user)
            if conv is None:
                raise ConversationNotFound(str(conversation_id))
        lang = normalize_language(language or (conv.language if conv else None))
        history = await self.repo.get_history(conv.id, HISTORY_LIMIT) if conv else []

        await self._resolve_active_model()
        triage = await classify(message, lang, llm=self.triage_llm)
        streamed = ""

        if triage.is_crisis:
            out = await self._crisis(triage, lang)
        elif triage.category == str(Category.social):
            acc: list[str] = []
            try:
                async for tok in self._stream_tokens(self._social_messages(history, message, lang)):
                    acc.append(tok); streamed += tok
                    yield {"event": "delta", "data": tok}
                answer = "".join(acc).strip()
                if not answer:
                    raise ValueError("empty social reply")
            except Exception:  # noqa: BLE001
                answer = await self._social_fallback(user, lang)
            out = _Outcome(answer, [], {"crisis": False, "needs_referral": False,
                                        "in_knowledge": None, "guard_reason": "social"})
        elif not triage.in_scope:
            acc = []
            try:
                async for tok in self._stream_tokens(self._offscope_messages(history, message, lang)):
                    acc.append(tok); streamed += tok
                    yield {"event": "delta", "data": tok}
                answer = "".join(acc).strip()
                if not answer:
                    raise ValueError("empty off-scope reply")
            except Exception:  # noqa: BLE001
                answer = t("out_of_scope", lang)
            out = _Outcome(answer, [], {"crisis": False, "needs_referral": False,
                                        "in_knowledge": None, "guard_reason": "out_of_scope"})
        else:
            try:
                retrieval = await self._retrieve_ranked(message, lang)
                profile = await ProfileService(self.session).get(user)
            except Exception as exc:  # noqa: BLE001
                logger.error("chat retrieval failed (%s); degrading", type(exc).__name__)
                await self.session.rollback()
                out = await self._degraded(triage, lang)
            else:
                if not retrieval.in_knowledge:
                    out = await self._degraded(triage, lang)
                else:
                    messages = assemble(message, retrieval, history, profile, lang)
                    acc, failed = [], False
                    # Sensitive topics (HIV/STI, pregnancy, abortion, GBV, crisis) may be REPLACED
                    # by the guard when ungrounded, so they are generated fully first and never
                    # streamed raw. Everything else streams live token-by-token.
                    if guard.is_sensitive(triage):
                        try:
                            acc.append(await self._generate(messages))
                        except Exception as exc:  # noqa: BLE001
                            logger.error("chat generation failed (%s); degrading", type(exc).__name__)
                            failed = True
                    else:
                        try:
                            async for tok in self._stream_tokens(messages):
                                acc.append(tok)
                                # Gate: never stream content that must be replaced (dosage / legal).
                                if guard.is_hard_unsafe("".join(acc)):
                                    break
                                streamed += tok
                                yield {"event": "delta", "data": tok}
                        except Exception as exc:  # noqa: BLE001
                            logger.error("chat generation failed (%s); degrading", type(exc).__name__)
                            failed = True
                    if failed:
                        await self.session.rollback()
                        out = await self._degraded(triage, lang)
                    else:
                        raw = "".join(acc)
                        g = guard.ground(raw, retrieval, language=lang, category=triage)
                        answer = g.answer
                        sensitive = guard.is_sensitive(triage) or triage.low_confidence
                        if g.needs_referral or sensitive:
                            refs = await self._referrals(triage)
                            answer = guard.ensure_referral(answer, triage, refs, language=lang,
                                                           force=g.needs_referral)
                        out = _Outcome(answer, _citations(g.answer, retrieval) if g.allowed else [],
                                       {"crisis": False, "needs_referral": g.needs_referral or sensitive,
                                        "in_knowledge": retrieval.in_knowledge, "guard_reason": g.reason})

        # If the final (guarded) answer differs from what was streamed, tell the client to swap.
        if out.answer != streamed:
            yield {"event": "replace", "data": out.answer}
        flags = self._build_flags(out, triage)
        result = await self._persist(user, conv, message, out, flags, lang)
        yield {"event": "done", "data": result.to_dict()}
