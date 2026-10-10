import json
import uuid

import pytest
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.core.db import get_engine, get_sessionmaker
from app.core.i18n import t
from app.models import Document, User
from app.models.conversation import Conversation, Message
from app.providers.fakes import FakeLLM
from app.services.chat import ChatService, ConversationNotFound
from tests.rag.test_retrieval import T_FP, _doc
from tests.test_identity import schema as _schema  # noqa: F401


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


@pytest.fixture
async def user(session):
    u = User(anon_id=f"chat-{uuid.uuid4().hex}")
    session.add(u)
    await session.commit()
    return u


async def test_grounded_answer_has_citations(session, user):
    await _doc(session, "FP Guide", [T_FP])
    llm = FakeLLM(["Condoms and pills are common methods ", "[S1]."])
    r = await ChatService(session, llm=llm).respond(user, T_FP, language="en")
    assert "[S1]" in r.answer and r.answer.startswith("Condoms")
    assert [c["id"] for c in r.citations] == ["S1"] and r.citations[0]["title"] == "FP Guide"
    assert r.safety_flags["in_knowledge"] is True and r.safety_flags["crisis"] is False
    assert not r.safety_flags["needs_referral"]
    msgs = (await session.execute(select(Message).where(
        Message.conversation_id == r.conversation_id).order_by(Message.created_at))).scalars().all()
    assert [m.role.value for m in msgs] == ["user", "assistant"]
    assert msgs[1].citations[0]["id"] == "S1" and msgs[1].safety_flags["category"]
    conv = await session.get(Conversation, r.conversation_id)
    assert conv.last_message_at is not None


async def test_out_of_knowledge_refers_to_doctor(session, user):
    await _doc(session, "FP Guide", [T_FP])
    llm = FakeLLM(["Sure, the answer is definitely 42 and you should do X."])
    r = await ChatService(session, llm=llm).respond(user, "How do I deal with an unusual rash?", language="en")
    assert t("disclaimer", "en") in r.answer
    assert "42" not in r.answer  # no fabrication
    assert t("referral_fallback", "en") in r.answer  # actionable referral
    assert r.citations == [] and r.safety_flags["needs_referral"] is True
    assert r.safety_flags["in_knowledge"] is False


async def test_crisis_input_bypasses_rag_and_refers(session, user, monkeypatch):
    import app.services.chat as chat_mod

    async def boom(*a, **k):
        raise AssertionError("retrieval must not run for crisis")

    monkeypatch.setattr(chat_mod, "retrieve", boom)
    llm = FakeLLM(["MODEL ANSWER MUST NOT APPEAR"])
    r = await ChatService(session, llm=llm).respond(user, "I want to kill myself", language="en")
    assert llm.calls == []  # no generation (rules-level crisis is final, so no triage LLM call either)
    assert "MODEL ANSWER" not in r.answer
    assert t("crisis_self_harm", "en") in r.answer
    assert t("referral_fallback", "en") in r.answer or t("referral_intro", "en") in r.answer
    assert r.safety_flags["crisis"] is True and r.safety_flags["category"] == "crisis_self_harm"
    stored = (await session.execute(select(Message).where(
        Message.conversation_id == r.conversation_id, Message.role == "assistant"))).scalar_one()
    assert stored.safety_flags["crisis"] is True


async def test_sensitive_uncited_answer_is_replaced(session, user):
    await _doc(session, "STI", ["Syphilis and other STIs are treated with antibiotics."])
    llm = FakeLLM(["You probably have an STI and should just take some pills."])
    r = await ChatService(session, llm=llm).respond(
        user, "Syphilis and other STIs are treated with antibiotics.", language="en")
    assert "take some pills" not in r.answer
    assert t("disclaimer", "en") in r.answer


async def test_stream_yields_sse_chunks(client, session, monkeypatch):
    import app.services.chat as chat_mod
    await _doc(session, "FP Guide", [T_FP])
    anon = (await client.post("/v1/identity/anon")).json()
    h = {"Authorization": f"Bearer {anon['access_token']}"}
    monkeypatch.setattr(chat_mod, "get_llm", lambda: FakeLLM(["Condoms work well [S1]."]))
    r = await client.post("/v1/chat/stream", json={"message": T_FP}, headers=h)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    assert "event: delta" in r.text and "event: done" in r.text
    done = r.text.split("event: done\ndata: ")[1].split("\n\n")[0]
    assert json.loads(done)["citations"][0]["id"] == "S1"
    # crisis: only the crisis/referral copy is streamed, never the model output
    monkeypatch.setattr(chat_mod, "get_llm", lambda: FakeLLM(["UNGUARDED MODEL OUTPUT"]))
    r = await client.post("/v1/chat/stream", json={"message": "I want to kill myself"}, headers=h)
    assert "UNGUARDED" not in r.text and "your life matters" in r.text
    # sensitive + uncited: replaced before any chunk is emitted
    await _doc(session, "STI", ["Syphilis and other STIs are treated with antibiotics."])
    r = await client.post("/v1/chat/stream", headers=h, json={
        "message": "Syphilis and other STIs are treated with antibiotics."})
    assert "UNGUARDED" not in r.text and "verified information" in r.text


async def test_chat_json_endpoint_auth_and_ownership(client, session, monkeypatch):
    import app.services.chat as chat_mod
    monkeypatch.setattr(chat_mod, "get_llm", lambda: FakeLLM(["x"]))
    assert (await client.post("/v1/chat", json={"message": "hi"})).status_code == 401
    a = (await client.post("/v1/identity/anon")).json()
    b = (await client.post("/v1/identity/anon")).json()
    ha, hb = ({"Authorization": f"Bearer {x['access_token']}"} for x in (a, b))
    r = await client.post("/v1/chat", json={"message": "hello there"}, headers=ha)
    assert r.status_code == 200 and r.json()["conversation_id"]
    cid = r.json()["conversation_id"]
    r2 = await client.post("/v1/chat", json={"message": "again", "conversation_id": cid}, headers=hb)
    assert r2.status_code == 404
    r3 = await client.post("/v1/chat", json={"message": "again", "conversation_id": cid}, headers=ha)
    assert r3.status_code == 200 and r3.json()["conversation_id"] == cid


async def test_unknown_conversation_raises(session, user):
    with pytest.raises(ConversationNotFound):
        await ChatService(session, llm=FakeLLM()).respond(user, "hi", uuid.uuid4())


async def test_response_language_honored(session, user):
    en = await ChatService(session, llm=FakeLLM()).respond(user, "I want to kill myself", language="en")
    rw = await ChatService(session, llm=FakeLLM()).respond(user, "I want to kill myself", language="rw")
    assert t("crisis_self_harm", "en") in en.answer and en.language == "en"
    assert t("crisis_self_harm", "rw") in rw.answer and rw.language == "rw"
    assert en.answer != rw.answer
    # out-of-knowledge disclaimer follows the language too
    r = await ChatService(session, llm=FakeLLM(["x"])).respond(user, "Ibibazo bidasanzwe?", language="rw")
    assert t("disclaimer", "rw") in r.answer and t("referral_fallback", "rw") in r.answer
