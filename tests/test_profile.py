import base64
import uuid

import pytest
from sqlalchemy import select, text

from app.core import crypto
from app.core.config import get_settings
from app.core.db import get_engine, get_sessionmaker
from app.models import User
from app.models.conversation import Conversation, Message, MessageRole
from app.models.profile import Profile
from app.services.profile import ProfileService
from tests.test_identity import schema as _schema  # noqa: F401


@pytest.fixture(scope="module", autouse=True)
def schema(_schema):
    return _schema


@pytest.fixture(autouse=True)
async def _fresh_pool(schema):
    # Other modules drop/recreate the schema; discard pooled connections whose
    # cached type OIDs are stale.
    await get_engine().dispose()
    yield


@pytest.fixture
async def session():
    async with get_sessionmaker()() as s:
        yield s


async def _anon(client):
    r = (await client.post("/v1/identity/anon")).json()
    return {"Authorization": f"Bearer {r['access_token']}"}


def test_crypto_roundtrip():
    blob = crypto.encrypt("I am anxious about X")
    assert isinstance(blob, bytes)
    assert b"anxious" not in blob
    assert crypto.decrypt(blob) == "I am anxious about X"
    assert crypto.encrypt("same") != crypto.encrypt("same")  # fresh nonce
    tampered = bytearray(blob)
    tampered[-1] ^= 0x01
    with pytest.raises(crypto.DecryptionError):
        crypto.decrypt(bytes(tampered))
    with pytest.raises(crypto.DecryptionError):
        crypto.decrypt(b"short")


def test_crypto_requires_valid_key(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "encryption_key", "")
    with pytest.raises(crypto.EncryptionKeyError):
        crypto.encrypt("x")
    monkeypatch.setattr(s, "encryption_key", base64.b64encode(b"short").decode())
    with pytest.raises(crypto.EncryptionKeyError):
        crypto.encrypt("x")
    monkeypatch.setattr(s, "encryption_key", "not base64 !!!")
    with pytest.raises(crypto.EncryptionKeyError):
        crypto.encrypt("x")


async def test_get_put_profile(client):
    h = await _anon(client)
    assert (await client.get("/v1/profile", headers=h)).status_code == 404
    r = await client.put("/v1/profile", headers=h, json={
        "nickname": "Amani", "age_band": "18_19", "gender": "female",
        "pronouns": "she/her", "tone_pref": "friendly", "interests": ["health", "music"]})
    assert r.status_code == 200, r.text
    g = (await client.get("/v1/profile", headers=h)).json()
    assert g["nickname"] == "Amani" and g["age_band"] == "18_19"
    assert g["interests"] == ["health", "music"]
    assert g["sensitive_context"] is None
    # partial update keeps other fields
    await client.put("/v1/profile", headers=h, json={"nickname": "Neza"})
    g = (await client.get("/v1/profile", headers=h)).json()
    assert g["nickname"] == "Neza" and g["tone_pref"] == "friendly"
    assert (await client.get("/v1/profile")).status_code == 401


async def test_sensitive_context_stored_encrypted(client, session):
    h = await _anon(client)
    secret = "I live with a chronic condition and fear my family finding out"
    r = await client.put("/v1/profile", headers=h, json={"nickname": "A", "sensitive_context": secret})
    assert r.status_code == 200, r.text
    assert r.json()["sensitive_context"] == secret
    assert "sensitive_context_enc" not in r.json()
    uid = (await session.execute(
        select(User.id).order_by(User.created_at.desc()).limit(1))).scalar_one()
    raw = (await session.execute(
        text("select sensitive_context_enc, consent from profiles where user_id=:u"),
        {"u": uid})).one()
    assert bytes(raw[0]) != secret.encode() and b"chronic" not in bytes(raw[0])
    assert raw[1]["sensitive_context"]["granted"] is True
    assert raw[1]["sensitive_context"]["at"]
    g = (await client.get("/v1/profile", headers=h)).json()
    assert g["sensitive_context"] == secret
    # explicit null clears it and revokes consent
    await client.put("/v1/profile", headers=h, json={"sensitive_context": None})
    g = (await client.get("/v1/profile", headers=h)).json()
    assert g["sensitive_context"] is None
    assert g["consent"]["sensitive_context"]["granted"] is False


async def test_wipe_clears_profile_and_history(client, session):
    h = await _anon(client)
    other = await _anon(client)
    await client.put("/v1/profile", headers=h, json={"nickname": "A", "sensitive_context": "x"})
    await client.put("/v1/profile", headers=other, json={"nickname": "B"})
    users = (await session.execute(
        select(User).order_by(User.created_at.desc()).limit(2))).scalars().all()
    other_u, me = users[0], users[1]
    other_id, me_id = other_u.id, me.id
    for u in (me, other_u):
        c = Conversation(user_id=u.id)
        session.add(c)
        await session.flush()
        session.add_all([Message(conversation_id=c.id, role=MessageRole.user, content="hi"),
                         Message(conversation_id=c.id, role=MessageRole.assistant, content="yo")])
    await session.commit()

    r = await client.delete("/v1/profile", headers=h)
    assert r.status_code == 204
    session.expire_all()
    assert await session.get(Profile, me_id) is None
    assert (await session.execute(
        select(Conversation).where(Conversation.user_id == me_id))).first() is None
    assert (await session.execute(text(
        "select count(*) from messages m join conversations c on c.id=m.conversation_id "
        "where c.user_id=:u"), {"u": me_id})).scalar_one() == 0
    # account itself survives; other user's data untouched
    assert await session.get(User, me_id) is not None
    assert await session.get(Profile, other_id) is not None
    assert (await session.execute(
        select(Conversation).where(Conversation.user_id == other_id))).first() is not None
    assert (await client.get("/v1/profile", headers=h)).status_code == 404
    assert (await client.delete("/v1/profile", headers=h)).status_code == 204  # idempotent
