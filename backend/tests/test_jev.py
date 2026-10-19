"""Jev integration logic — offline (no network, SDK stubbed). Covers triage refinement,
confidence gating, passage filtering/re-rank, and the fail-soft (Jev-off) path."""
import pytest

import app.providers.jev as jevmod
from app.providers.jev import JevTriage, PassageVerdict
from app.rag.jev_rerank import rerank
from app.rag.retrieval import RetrievalResult, RetrievedChunk
from app.safety import triage as triagemod
from app.safety.triage import Category, classify
import uuid


class FakeJev:
    """Stand-in for JevClient with scripted answers; no SDK / network."""
    def __init__(self, triage=None, verdicts=None, on=True):
        self.triage_enabled = on
        self.rerank_enabled = on
        self._triage = triage
        self._verdicts = verdicts or {}  # title -> PassageVerdict

    def status(self):
        return {"configured": self._triage is not None, "model": "jev-test"}

    async def triage(self, text):
        return self._triage

    async def filter_passages(self, query, passages):
        if not self.rerank_enabled:
            return None
        from app.core.config import get_settings
        s = get_settings()
        out = []
        for i, (title, _text) in enumerate(passages):
            v = self._verdicts.get(title)
            if v is not None and v.accept(s):
                out.append((i, v))
        out.sort(key=lambda iv: iv[1].relevant, reverse=True)
        return out


@pytest.fixture
def install_jev(monkeypatch):
    def _install(fake):
        monkeypatch.setattr(jevmod, "_SINGLETON", fake)
    yield _install
    monkeypatch.setattr(jevmod, "_SINGLETON", None)


def _chunk(title, content, score):
    return RetrievedChunk(content=content, document_id=uuid.uuid4(), title=title, score=score)


# ---- triage -------------------------------------------------------------------------

async def test_jev_escalates_bare_message_to_crisis(install_jev):
    install_jev(FakeJev(triage=JevTriage("crisis_self_harm", 0.9)))
    # A message rules would treat as bare in-scope; Jev escalates to crisis.
    t = await classify("i don't know why i'm here anymore", "en")
    assert t.is_crisis and t.category == str(Category.crisis_self_harm) and t.source == "jev"


async def test_jev_refines_bare_in_scope_to_out_of_scope(install_jev):
    install_jev(FakeJev(triage=JevTriage("out_of_scope", 0.95)))
    t = await classify("can you help me with this", "en")
    assert t.category == str(Category.out_of_scope) and not t.in_scope and t.source == "jev"


async def test_jev_low_confidence_sets_flag(install_jev):
    install_jev(FakeJev(triage=JevTriage("in_scope_srhr", 0.3)))
    t = await classify("something about my body idk", "en")
    assert t.in_scope and t.low_confidence and t.confidence == pytest.approx(0.3)


async def test_rules_crisis_is_never_downgraded_by_jev(install_jev):
    # Jev says social, but the rules already found self-harm -> crisis stands, Jev not consulted.
    install_jev(FakeJev(triage=JevTriage("social", 0.99)))
    t = await classify("I want to kill myself", "en")
    assert t.is_crisis and t.source == "rules"


async def test_triage_falls_back_to_llm_when_jev_off(install_jev, monkeypatch):
    install_jev(FakeJev(on=False))
    called = {}

    async def fake_llm_label(text, llm):
        called["hit"] = True
        return None

    monkeypatch.setattr(triagemod, "_llm_label", fake_llm_label)
    await classify("tell me about puberty", "en")
    assert called.get("hit")  # LLM fallback was used because Jev was disabled


# ---- passage filtering / re-rank ----------------------------------------------------

async def test_rerank_drops_injection_and_irrelevant_and_sorts(install_jev):
    verdicts = {
        "good":      PassageVerdict(relevant=0.9, evidence=0.9, injection=0.0),
        "ok":        PassageVerdict(relevant=0.8, evidence=0.6, injection=0.0),
        "injected":  PassageVerdict(relevant=0.9, evidence=0.9, injection=0.95),
        "irrelevant": PassageVerdict(relevant=0.1, evidence=0.1, injection=0.0),
    }
    install_jev(FakeJev(verdicts=verdicts))
    r = RetrievalResult(
        chunks=[_chunk("ok", "...", 0.5), _chunk("injected", "...", 0.9),
                _chunk("good", "...", 0.4), _chunk("irrelevant", "...", 0.8)],
        max_score=0.9, in_knowledge=True)
    out = await rerank("q", r)
    titles = [c.title for c in out.chunks]
    assert titles == ["good", "ok"]  # injected + irrelevant dropped, sorted by relevance desc
    assert out.in_knowledge


async def test_rerank_all_dropped_becomes_out_of_knowledge(install_jev):
    verdicts = {"a": PassageVerdict(0.1, 0.1, 0.0)}
    install_jev(FakeJev(verdicts=verdicts))
    r = RetrievalResult(chunks=[_chunk("a", "...", 0.5)], max_score=0.5, in_knowledge=True)
    out = await rerank("q", r)
    assert out.chunks == [] and not out.in_knowledge


async def test_rerank_noop_when_jev_off(install_jev):
    install_jev(FakeJev(on=False))
    r = RetrievalResult(chunks=[_chunk("a", "...", 0.5)], max_score=0.5, in_knowledge=True)
    out = await rerank("q", r)
    assert out is r  # unchanged object -> pipeline behaves exactly as before
