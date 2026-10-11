import pathlib
import uuid

import pytest
from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.db import get_engine, get_sessionmaker
from app.models import DocStatus, Document, DocumentChunk, ReviewStatus
from app.providers.fakes import FakeEmbeddings
from app.rag.extract import ExtractionError, extract_text
from app.repositories.documents import DocumentRepository
from app.services.ingestion import IngestionService
from tests.test_identity import schema as _schema  # noqa: F401

FIX = pathlib.Path(__file__).parent.parent / "fixtures"


@pytest.fixture(scope="module", autouse=True)
def schema(_schema):
    return _schema


@pytest.fixture(autouse=True)
async def _fresh_pool(schema):
    await get_engine().dispose()
    yield


@pytest.fixture(autouse=True)
def _storage(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "storage_dir", str(tmp_path))


@pytest.fixture
async def session():
    async with get_sessionmaker()() as s:
        yield s


@pytest.fixture
def svc(session):
    return IngestionService(session, embeddings=FakeEmbeddings())


async def _chunks(session, doc_id):
    r = await session.execute(
        select(DocumentChunk).where(DocumentChunk.document_id == doc_id)
        .order_by(DocumentChunk.chunk_index))
    return list(r.scalars())


def test_extract_pages():
    pages = extract_text((FIX / "sample.pdf").read_bytes())
    assert [p.page_number for p in pages] == [1, 2]
    assert "contraception" in pages[0].text.lower()


@pytest.mark.parametrize("data", [b"", b"not a pdf at all", (FIX / "empty.pdf").read_bytes()])
def test_extract_bad_raises(data):
    with pytest.raises(ExtractionError):
        extract_text(data)


async def test_ingest_pdf_creates_chunks_with_embeddings(svc, session, tmp_path):
    data = (FIX / "sample.pdf").read_bytes()
    doc = await svc.create_document("Contraception", "sample.pdf", data, language="en",
                                    topic_tags=["fp"])
    assert doc.status == DocStatus.uploaded and doc.review_status == ReviewStatus.pending
    assert doc.checksum and len(doc.checksum) == 64
    assert (tmp_path / f"{doc.id}.pdf").read_bytes() == data
    await svc.ingest(doc.id)
    await session.refresh(doc)
    assert doc.status == DocStatus.indexed and doc.indexed_at is not None
    chunks = await _chunks(session, doc.id)
    assert chunks
    for c in chunks:
        assert len(c.embedding) == 768
        assert c.token_count > 0 and c.language == "en" and c.meta["page"] in (1, 2)


@pytest.mark.parametrize("data", [b"garbage bytes", (FIX / "empty.pdf").read_bytes(), b""])
async def test_empty_or_bad_pdf_marks_failed(svc, session, data):
    doc = await svc.create_document("Bad", "bad.pdf", data)
    await svc.ingest(doc.id)  # must not raise
    await session.refresh(doc)
    assert doc.status == DocStatus.failed
    assert doc.review_notes and "ingest failed" in doc.review_notes
    assert await _chunks(session, doc.id) == []


async def test_embedding_failure_leaves_no_partial_chunks(session):
    class Boom:
        async def embed(self, texts, kind):
            raise RuntimeError("model down")

    svc = IngestionService(session, embeddings=Boom())
    doc = await svc.create_document("T", "s.pdf", (FIX / "sample.pdf").read_bytes())
    await svc.ingest(doc.id)
    await session.refresh(doc)
    assert doc.status == DocStatus.failed
    assert await _chunks(session, doc.id) == []


async def test_only_approved_docs_retrievable(svc, session):
    data = (FIX / "sample.pdf").read_bytes()
    docs = {}
    for name in ("pending", "approved", "rejected"):
        d = await svc.create_document(name, f"{name}.pdf", data)
        await svc.ingest(d.id)
        docs[name] = d
    reviewer = None
    await svc.set_review(docs["approved"].id, ReviewStatus.approved, reviewer, "ok")
    await svc.set_review(docs["rejected"].id, ReviewStatus.rejected, reviewer, "bad")

    ids = {d.id for d in docs.values()}
    repo = DocumentRepository(session)
    stmt = repo.approved_chunks_stmt().where(DocumentChunk.document_id.in_(ids))
    rows = (await session.execute(stmt)).scalars().all()
    assert rows and {c.document_id for c in rows} == {docs["approved"].id}

    # Unapproving removes retrievability again.
    await svc.set_review(docs["approved"].id, ReviewStatus.pending)
    rows = (await session.execute(stmt)).scalars().all()
    assert rows == []
    await session.refresh(docs["rejected"])
    assert docs["rejected"].review_notes == "bad"


async def test_failed_approved_doc_not_retrievable(svc, session):
    d = await svc.create_document("x", "x.pdf", b"garbage")
    await svc.ingest(d.id)
    await svc.set_review(d.id, ReviewStatus.approved)
    stmt = DocumentRepository(session).approved_chunks_stmt().where(
        DocumentChunk.document_id == d.id)
    assert (await session.execute(stmt)).scalars().all() == []


async def test_reindex_replaces_chunks(svc, session):
    d = await svc.create_document("R", "r.pdf", (FIX / "sample.pdf").read_bytes())
    await svc.ingest(d.id)
    old = {c.id for c in await _chunks(session, d.id)}
    assert old
    await svc.reindex(d.id)
    await session.refresh(d)
    new = await _chunks(session, d.id)
    assert d.version == 2 and d.status == DocStatus.indexed
    assert len(new) == len(old) and not ({c.id for c in new} & old)
    assert [c.chunk_index for c in new] == list(range(len(new)))
    total = (await session.execute(
        select(func.count()).select_from(DocumentChunk)
        .where(DocumentChunk.document_id == d.id))).scalar_one()
    assert total == len(new)


async def test_unknown_document(svc):
    with pytest.raises(LookupError):
        await svc.ingest(uuid.uuid4())
