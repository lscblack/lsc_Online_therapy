import pathlib
import uuid

import pytest
from sqlalchemy import delete, func, select

from app.core.config import get_settings
from app.core.db import get_engine, get_sessionmaker
from app.core.security import create_access_token, hash_secret
from app.models import AppSetting, AuditLog, Document, DocumentChunk, User
from app.models.user import UserRole
from app.repositories.documents import DocumentRepository
from tests.test_identity import schema as _schema  # noqa: F401

PDF = (pathlib.Path(__file__).parent / "fixtures" / "sample.pdf").read_bytes()
PW = "correct-horse-battery"


@pytest.fixture(scope="module", autouse=True)
def schema(_schema):
    return _schema


@pytest.fixture(autouse=True)
async def _fresh_pool(schema):
    await get_engine().dispose()
    yield


@pytest.fixture(autouse=True)
def _env(monkeypatch, tmp_path):
    s = get_settings()
    monkeypatch.setattr(s, "embedding_provider", "fake")
    monkeypatch.setattr(s, "storage_dir", str(tmp_path))


@pytest.fixture
async def session():
    async with get_sessionmaker()() as s:
        await s.execute(delete(Document))
        await s.execute(delete(AppSetting))
        await s.commit()
        yield s
        await s.rollback()
        await s.execute(delete(Document))
        await s.execute(delete(AppSetting))
        await s.commit()


async def _mk(session, role, email=None):
    u = User(anon_id=f"adm-{uuid.uuid4().hex}", role=role, email=email,
             password_hash=hash_secret(PW) if email else None)
    session.add(u)
    await session.commit()
    await session.refresh(u)
    tok = create_access_token(str(u.id), u.role.value)
    u.headers = {"Authorization": f"Bearer {tok}"}
    u.email_ = email
    u.uid = u.id
    return u


def _h(u):
    return u.headers


@pytest.fixture
async def admin(session):
    return await _mk(session, UserRole.admin, f"a-{uuid.uuid4().hex}@x.org")


@pytest.fixture
async def reviewer(session):
    return await _mk(session, UserRole.reviewer, f"r-{uuid.uuid4().hex}@x.org")


@pytest.fixture
async def plain(session):
    return await _mk(session, UserRole.user)


async def _upload(client, headers, title="Contraception guide"):
    return await client.post(
        "/v1/admin/documents", headers=headers,
        data={"title": title, "language": "en", "topic_tags": "contraception,family"},
        files={"file": ("sample.pdf", PDF, "application/pdf")})


async def _chunk_count(session, doc_id):
    return (await session.execute(select(func.count()).select_from(DocumentChunk)
            .where(DocumentChunk.document_id == doc_id))).scalar_one()


async def _retrievable(session, doc_id):
    stmt = DocumentRepository.approved_chunks_stmt().where(DocumentChunk.document_id == doc_id)
    return len((await session.execute(stmt)).scalars().all())


async def _audit(session, action, actor):
    session.expire_all()
    r = await session.execute(select(AuditLog).where(
        AuditLog.action == action, AuditLog.actor_id == actor.uid))
    return list(r.scalars())


async def test_upload_then_review_then_retrievable(client, session, admin, reviewer):
    r = await _upload(client, _h(admin))
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "indexed" and body["review_status"] == "pending"
    assert body["topic_tags"] == ["contraception", "family"]
    doc_id = uuid.UUID(body["id"])
    assert await _chunk_count(session, doc_id) > 0
    assert await _retrievable(session, doc_id) == 0  # pending -> not retrievable

    r = await client.post(f"/v1/admin/documents/{doc_id}/review", headers=_h(reviewer),
                          json={"status": "approved", "notes": "ok"})
    assert r.status_code == 200 and r.json()["review_status"] == "approved"
    session.expire_all()
    assert await _retrievable(session, doc_id) > 0

    assert (await client.get("/v1/admin/documents", headers=_h(reviewer))).status_code == 200
    got = await client.get(f"/v1/admin/documents/{doc_id}", headers=_h(reviewer))
    assert got.json()["id"] == str(doc_id)
    assert (await client.get(f"/v1/admin/documents/{uuid.uuid4()}",
                             headers=_h(admin))).status_code == 404


async def test_upload_failed_ingest_surfaces_status(client, admin):
    r = await client.post("/v1/admin/documents", headers=_h(admin), data={"title": "bad"},
                          files={"file": ("bad.pdf", b"not a pdf", "application/pdf")})
    assert r.status_code == 201
    assert r.json()["status"] == "failed"


async def test_upload_rejects_empty_and_oversize(client, admin, monkeypatch):
    r = await client.post("/v1/admin/documents", headers=_h(admin), data={"title": "e"},
                          files={"file": ("e.pdf", b"", "application/pdf")})
    assert r.status_code == 400
    monkeypatch.setattr("app.api.v1.admin.MAX_PDF_BYTES", 10)
    r = await _upload(client, _h(admin))
    assert r.status_code == 413


async def test_reindex(client, session, admin):
    doc_id = uuid.UUID((await _upload(client, _h(admin))).json()["id"])
    session.expire_all()
    old = set((await session.execute(select(DocumentChunk.id)
               .where(DocumentChunk.document_id == doc_id))).scalars())
    assert old
    r = await client.post(f"/v1/admin/documents/{doc_id}/reindex", headers=_h(admin))
    assert r.status_code == 200 and r.json()["version"] == 2
    session.expire_all()
    new = set((await session.execute(select(DocumentChunk.id)
               .where(DocumentChunk.document_id == doc_id))).scalars())
    assert new and not (old & new)


async def test_non_admin_forbidden(client, session, admin, plain, reviewer):
    doc_id = uuid.UUID((await _upload(client, _h(admin))).json()["id"])
    uh = _h(plain)
    calls = [
        ("post", "/v1/admin/documents", {"data": {"title": "x"},
                                         "files": {"file": ("a.pdf", PDF, "application/pdf")}}),
        ("get", "/v1/admin/documents", {}),
        ("get", f"/v1/admin/documents/{doc_id}", {}),
        ("post", f"/v1/admin/documents/{doc_id}/review", {"json": {"status": "approved"}}),
        ("post", f"/v1/admin/documents/{doc_id}/reindex", {}),
        ("delete", f"/v1/admin/documents/{doc_id}", {}),
        ("get", "/v1/admin/users", {}),
        ("post", f"/v1/admin/users/{plain.uid}/disable", {}),
        ("get", "/v1/admin/audit", {}),
    ]
    for m, url, kw in calls:
        r = await getattr(client, m)(url, headers=uh, **kw)
        assert r.status_code == 403, (m, url, r.status_code)
        r = await getattr(client, m)(url, **kw)
        assert r.status_code == 401, (m, url, r.status_code)
    # reviewer may not do admin-only actions
    rh = _h(reviewer)
    for m, url in [("delete", f"/v1/admin/documents/{doc_id}"), ("get", "/v1/admin/users"),
                   ("get", "/v1/admin/audit"),
                   ("post", f"/v1/admin/users/{plain.uid}/disable")]:
        assert (await getattr(client, m)(url, headers=rh)).status_code == 403, url
    session.expire_all()
    assert await session.get(Document, doc_id) is not None
    assert not (await session.get(User, plain.uid)).disabled


async def test_role_from_db_not_token(client, plain):
    forged = create_access_token(str(plain.uid), "admin")
    r = await client.get("/v1/admin/users", headers={"Authorization": f"Bearer {forged}"})
    assert r.status_code == 403


async def test_actions_are_audited(client, session, admin, reviewer, plain):
    doc_id = (await _upload(client, _h(admin))).json()["id"]
    await client.post(f"/v1/admin/documents/{doc_id}/review", headers=_h(reviewer),
                      json={"status": "rejected", "notes": "no"})
    await client.post(f"/v1/admin/documents/{doc_id}/reindex", headers=_h(admin))
    r = await client.post(f"/v1/admin/users/{plain.uid}/disable", headers=_h(admin))
    assert r.status_code == 200 and r.json()["disabled"] is True
    r = await client.delete(f"/v1/admin/documents/{doc_id}", headers=_h(admin))
    assert r.status_code == 204
    session.expire_all()
    assert await session.get(Document, uuid.UUID(doc_id)) is None
    assert not list(pathlib.Path(get_settings().storage_dir).glob(f"{doc_id}.pdf"))
    for action, actor in [("document.upload", admin), ("document.review", reviewer),
                          ("document.reindex", admin), ("user.disable", admin),
                          ("document.delete", admin)]:
        rows = await _audit(session, action, actor)
        assert rows, action
    rev = (await _audit(session, "document.review", reviewer))[0]
    assert rev.target == doc_id and rev.meta["status"] == "rejected"

    r = await client.get("/v1/admin/audit?limit=5", headers=_h(admin))
    assert r.status_code == 200 and 0 < len(r.json()) <= 5
    r = await client.get("/v1/admin/users", headers=_h(admin))
    assert r.status_code == 200
    assert "password_hash" not in r.text and "recovery_hash" not in r.text


async def test_missing_targets_404(client, admin):
    ghost = uuid.uuid4()
    for m, url, kw in [("post", f"/v1/admin/documents/{ghost}/review",
                        {"json": {"status": "approved"}}),
                       ("post", f"/v1/admin/documents/{ghost}/reindex", {}),
                       ("delete", f"/v1/admin/documents/{ghost}", {}),
                       ("post", f"/v1/admin/users/{ghost}/disable", {})]:
        assert (await getattr(client, m)(url, headers=_h(admin), **kw)).status_code == 404


async def test_admin_login(client, admin, reviewer, plain):
    r = await client.post("/v1/admin/login", json={"email": admin.email_, "password": PW})
    assert r.status_code == 200
    tok = r.json()
    assert tok["access_token"] and tok["refresh_token"]
    ok = await client.get("/v1/admin/users",
                          headers={"Authorization": f"Bearer {tok['access_token']}"})
    assert ok.status_code == 200
    bad = [{"email": admin.email_, "password": "wrong-password"},
           {"email": "nobody@x.org", "password": PW}]
    for b in bad:
        assert (await client.post("/v1/admin/login", json=b)).status_code == 401


async def test_me_returns_authenticated_role(client, admin, reviewer, plain):
    r = await client.get("/v1/admin/me", headers=_h(admin))
    assert r.status_code == 200 and r.json()["role"] == "admin"
    r = await client.get("/v1/admin/me", headers=_h(reviewer))
    assert r.status_code == 200 and r.json()["role"] == "reviewer"
    assert r.json()["email"] == reviewer.email_
    assert (await client.get("/v1/admin/me", headers=_h(plain))).status_code == 403
    assert (await client.get("/v1/admin/me")).status_code == 401


# --- LLM model management ---------------------------------------------------

async def test_models_get_defaults_and_rbac(client, admin, reviewer, plain):
    r = await client.get("/v1/admin/models", headers=_h(admin))
    assert r.status_code == 200
    body = r.json()
    assert body["active"] == body["default"]          # no override yet
    assert body["is_override"] is False
    assert any(m["id"] == "inclusionai/ling-3.1-flash" for m in body["catalog"])
    # model management is admin-only
    assert (await client.get("/v1/admin/models", headers=_h(reviewer))).status_code == 403
    assert (await client.get("/v1/admin/models", headers=_h(plain))).status_code == 403
    assert (await client.get("/v1/admin/models")).status_code == 401


async def test_set_model_persists_and_audits(client, admin, session):
    r = await client.put("/v1/admin/models", headers=_h(admin),
                         json={"model": "openrouter/free"})
    assert r.status_code == 200
    assert r.json()["active"] == "openrouter/free" and r.json()["is_override"] is True
    # reflected on a fresh GET
    g = await client.get("/v1/admin/models", headers=_h(admin))
    assert g.json()["active"] == "openrouter/free"
    assert len(await _audit(session, "model.set", admin)) == 1


async def test_set_model_is_admin_only(client, reviewer, plain):
    assert (await client.put("/v1/admin/models", headers=_h(reviewer),
                             json={"model": "x"})).status_code == 403
    assert (await client.put("/v1/admin/models", headers=_h(plain),
                             json={"model": "x"})).status_code == 403


async def test_test_model_reports_ok_and_errors(client, admin, monkeypatch):
    import app.services.admin as adminmod

    class _FakeLLM:
        def __init__(self, text): self._t = text
        async def stream_chat(self, messages, **opts):
            for part in self._t.split():
                yield part + " "

    def fake_get_llm(settings=None, model=None):
        if model == "good/model":
            return _FakeLLM("condoms and the pill are options")
        raise RuntimeError("no endpoints for this model")

    monkeypatch.setattr(adminmod, "get_llm", fake_get_llm)

    ok = await client.post("/v1/admin/models/test", headers=_h(admin),
                           json={"model": "good/model", "prompt": "hi"})
    assert ok.status_code == 200 and ok.json()["ok"] is True
    assert "condoms" in ok.json()["sample"] and ok.json()["latency_ms"] >= 0

    bad = await client.post("/v1/admin/models/test", headers=_h(admin),
                            json={"model": "bad/model", "prompt": "hi"})
    assert bad.status_code == 200 and bad.json()["ok"] is False
    assert "no endpoints" in bad.json()["error"]
