import pytest
from sqlalchemy import delete

from app.core.config import get_settings
from app.core.db import get_engine, get_sessionmaker
from app.models import DocStatus, Document, ReviewStatus
from app.providers.fakes import FakeEmbeddings
from app.rag.retrieval import RetrievalResult, retrieve
from app.repositories.documents import DocumentRepository
from tests.test_identity import schema as _schema  # noqa: F401

T_FP = "Condoms and pills are common family planning methods."
T_STI = "Syphilis and other STIs are treated with antibiotics."
T_RW = "Agakingirizo k'inda kagufasha kwirinda gutwita."


@pytest.fixture(scope="module", autouse=True)
def schema(_schema):
    return _schema


@pytest.fixture(autouse=True)
async def _fresh_pool(schema):
    await get_engine().dispose()
    yield


@pytest.fixture(autouse=True)
def _fake_emb(monkeypatch):
    monkeypatch.setattr(get_settings(), "embedding_provider", "fake")


@pytest.fixture
async def session():
    async with get_sessionmaker()() as s:
        await s.execute(delete(Document))
        await s.commit()
        yield s
        await s.rollback()
        await s.execute(delete(Document))
        await s.commit()


async def _doc(session, title, texts, language="en", review=ReviewStatus.approved,
               status=DocStatus.indexed):
    repo = DocumentRepository(session)
    doc = await repo.create_document(title=title, language=language, review_status=review,
                                     status=status)
    embs = await FakeEmbeddings().embed(texts, "passage")
    await repo.add_chunks(doc.id, [
        dict(chunk_index=i, content=t, token_count=5, language=language,
             meta={"page": i + 1}, embedding=e)
        for i, (t, e) in enumerate(zip(texts, embs, strict=True))])
    await session.commit()
    return doc


async def test_retrieve_ranks_by_similarity(session):
    await _doc(session, "FP", [T_FP, T_STI])
    r = await retrieve(session, T_STI, k=2)
    assert isinstance(r, RetrievalResult)
    assert r.chunks[0].content == T_STI
    assert r.chunks[0].score == pytest.approx(1.0, abs=1e-3)
    assert r.chunks[0].score > r.chunks[1].score
    assert r.max_score == r.chunks[0].score
    assert r.chunks[0].title == "FP" and r.chunks[0].meta == {"page": 2}
    assert r.in_knowledge is True


async def test_language_filter(session):
    await _doc(session, "EN", [T_FP], language="en")
    await _doc(session, "RW", [T_RW], language="rw")
    r = await retrieve(session, T_FP, language="rw")
    assert [c.content for c in r.chunks] == [T_RW]
    r = await retrieve(session, T_FP, language="fr")  # no match -> fall back to all
    assert r.chunks and r.chunks[0].content == T_FP


async def test_below_threshold_marks_out_of_knowledge(session):
    await _doc(session, "FP", [T_FP, T_STI])
    r = await retrieve(session, "how do I fix my bicycle tyre")
    assert r.chunks and r.max_score < get_settings().retrieval_min_score
    assert r.in_knowledge is False


async def test_empty_corpus_out_of_knowledge(session):
    r = await retrieve(session, "anything")
    assert r.chunks == [] and r.max_score == 0.0 and r.in_knowledge is False


@pytest.mark.parametrize("lang", ["en-RW", "", "xx", "EN", "rw-RW", None, "mix"])
async def test_mixed_language_query_defaults_safely(session, lang):
    await _doc(session, "FP", [T_FP])
    r = await retrieve(session, "Mbwira about contraception ni iki? 你好", language=lang)
    assert isinstance(r, RetrievalResult) and r.chunks


async def test_only_approved_retrieved(session):
    await _doc(session, "pending", [T_FP], review=ReviewStatus.pending)
    await _doc(session, "rejected", [T_FP], review=ReviewStatus.rejected)
    await _doc(session, "failed", [T_FP], status=DocStatus.failed)
    r = await retrieve(session, T_FP)
    assert r.chunks == [] and r.in_knowledge is False
    await _doc(session, "ok", [T_FP])
    r = await retrieve(session, T_FP)
    assert [c.title for c in r.chunks] == ["ok"]
