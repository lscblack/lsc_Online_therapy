import json
import uuid

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app import cli
from app.api.lang import parse_accept_language
from app.core.config import get_settings
from app.core.db import get_engine, get_sessionmaker
from app.core.security import verify_secret
from app.main import app, seed_referrals_on_startup
from app.models import User
from app.models.referral import Referral
from app.models.user import UserRole
from tests.test_identity import schema as _schema  # noqa: F401


@pytest.fixture(scope="module", autouse=True)
def schema(_schema):
    return _schema


@pytest.fixture(autouse=True)
async def _fresh_pool(schema):
    await get_engine().dispose()
    yield


def test_all_routes_registered():
    paths = set(app.openapi()["paths"])
    for p in ["/v1/health", "/v1/identity/recover", "/v1/profile", "/v1/chat",
              "/v1/voice/chat", "/v1/admin/login"]:
        assert any(x == p or x.startswith(p) for x in paths), p


def test_live_ws_requires_auth():
    from starlette.websockets import WebSocketDisconnect
    with TestClient(app) as c:
        with pytest.raises(WebSocketDisconnect) as ei:
            with c.websocket_connect("/v1/live?session_id=x"):
                pass
        assert ei.value.code == 4401


async def test_error_envelope_shape(client):
    r = await client.get("/v1/nope")
    assert r.status_code == 404
    body = r.json()
    assert set(body) == {"error"} and body["error"]["code"] == "not_found"
    assert isinstance(body["error"]["message"], str)

    r = await client.post("/v1/identity/recover", json={"anon_id": 5, "passphrase": "SECRETVALUE"})
    assert r.status_code == 422
    e = r.json()["error"]
    assert e["code"] == "validation_error" and isinstance(e["details"], list)
    assert "SECRETVALUE" not in r.text  # inputs are never echoed back

    r = await client.get("/v1/chat/x")  # 404/405 variants stay enveloped
    assert "error" in r.json()


async def test_unhandled_error_is_generic():
    from fastapi import FastAPI

    from app.core.errors import install_error_handlers
    a = FastAPI()
    install_error_handlers(a)

    @a.get("/boom")
    async def boom():
        raise RuntimeError("db password=hunter2 /srv/secret.py")

    t = httpx.ASGITransport(app=a, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=t, base_url="http://t") as c:
        r = await c.get("/boom")
    assert r.status_code == 500
    assert r.json() == {"error": {"code": "internal_error", "message": "Internal server error"}}
    assert "hunter2" not in r.text and "Traceback" not in r.text


def test_accept_language_resolution():
    assert parse_accept_language("rw") == "rw"
    assert parse_accept_language("en-US,en;q=0.9") == "en"
    assert parse_accept_language("fr;q=0.9, rw-RW;q=0.8") == "rw"
    assert parse_accept_language("rw;q=0.2, en;q=0.9") == "en"
    assert parse_accept_language("fr, de") == "en"
    assert parse_accept_language(None) == "en"
    assert parse_accept_language("") == "en"


async def test_accept_language_header_used_by_endpoint(client, monkeypatch):
    from app.services.chat import ChatResult, ChatService
    seen = {}

    async def fake(self, user, message, cid, language=None):
        seen["lang"] = language
        return ChatResult(answer="x", citations=[], conversation_id=uuid.uuid4(),
                          safety_flags={}, language=language or "en")
    monkeypatch.setattr(ChatService, "respond", fake)
    tok = (await client.post("/v1/identity/anon")).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    await client.post("/v1/chat", json={"message": "hi"}, headers={**h, "Accept-Language": "rw"})
    assert seen["lang"] == "rw"
    await client.post("/v1/chat", json={"message": "hi", "language": "en"},
                      headers={**h, "Accept-Language": "rw"})
    assert seen["lang"] == "en"  # explicit body wins
    await client.post("/v1/chat", json={"message": "hi"})  # unauth
    await client.post("/v1/chat", json={"message": "hi"}, headers=h)
    assert seen["lang"] is None  # no header -> leave to service/conversation default


async def test_rate_limit_triggers(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "rate_limit_auth_per_min", 3)
    codes = []
    for _ in range(5):
        r = await client.post("/v1/admin/login", json={"email": "a@b.org", "password": "x" * 12})
        codes.append(r.status_code)
    assert codes[:3] == [401, 401, 401] and codes[3:] == [429, 429]
    assert r.json()["error"]["code"] == "rate_limited"
    assert "Retry-After" in r.headers

    codes = [(await client.post("/v1/identity/recover",
                                json={"anon_id": "a", "passphrase": "p" * 12})).status_code
             for _ in range(5)]
    assert codes[-1] == 429


async def test_rate_limit_chat_per_user(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "rate_limit_chat_per_min", 2)
    tok = (await client.post("/v1/identity/anon")).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    codes = [(await client.post("/v1/chat", json={"message": " "}, headers=h)).status_code
             for _ in range(3)]
    assert codes == [422, 422, 429]


async def _count_admin(email):
    async with get_sessionmaker()() as s:
        return (await s.execute(select(User).where(User.email == email))).scalars().all()


async def test_create_admin_cli():
    email = f"boot-{uuid.uuid4().hex[:8]}@x.org"
    async with get_sessionmaker()() as s:
        u = await cli.create_admin(s, email, "correct-horse-battery")
    assert u.role == UserRole.admin and u.email == email
    rows = await _count_admin(email)
    assert len(rows) == 1 and rows[0].password_hash != "correct-horse-battery"
    assert verify_secret("correct-horse-battery", rows[0].password_hash)
    async with get_sessionmaker()() as s:
        with pytest.raises(cli.AdminExists):
            await cli.create_admin(s, email.upper(), "another-long-password")
        with pytest.raises(ValueError):
            await cli.create_admin(s, "short@x.org", "short")
    assert len(await _count_admin(email)) == 1


def test_cli_main_exit_codes(monkeypatch, capsys):
    email = f"m-{uuid.uuid4().hex[:8]}@x.org"
    assert cli.main(["create_admin", "--email", email, "--password", "correct-horse-battery"]) == 0
    assert cli.main(["create_admin", "--email", email, "--password", "correct-horse-battery"]) == 1
    out = capsys.readouterr()
    assert "correct-horse-battery" not in out.out + out.err


async def test_startup_seed_idempotent_and_keeps_verified():
    async with get_sessionmaker()() as s:
        await s.execute(delete(Referral))
        await s.commit()
    assert await seed_referrals_on_startup() > 0
    async with get_sessionmaker()() as s:
        n1 = (await s.execute(select(func.count()).select_from(Referral))).scalar_one()
        row = (await s.execute(select(Referral).limit(1))).scalar_one()
        from datetime import UTC, datetime
        row.contact, row.verified_at = "VERIFIED-CONTACT", datetime.now(UTC)
        rid = row.id
        await s.commit()
    await seed_referrals_on_startup()
    async with get_sessionmaker()() as s:
        n2 = (await s.execute(select(func.count()).select_from(Referral))).scalar_one()
        assert n1 == n2 > 0
        assert (await s.get(Referral, rid)).contact == "VERIFIED-CONTACT"


async def test_startup_seed_survives_missing_schema(monkeypatch):
    class Boom:
        async def __aenter__(self):
            raise RuntimeError("relation does not exist")

        async def __aexit__(self, *a):
            return False
    monkeypatch.setattr("app.main.get_sessionmaker", lambda: (lambda: Boom()))
    assert await seed_referrals_on_startup() == 0


def _req(peer, xff=None):
    from starlette.requests import Request
    hdrs = [(b"x-forwarded-for", xff.encode())] if xff else []
    return Request({"type": "http", "headers": hdrs, "client": (peer, 1)})


def test_client_ip_proxy_handling(monkeypatch):
    from app.core.ratelimit import _client_ip
    s = get_settings()
    monkeypatch.setattr(s, "trusted_proxies", "")
    assert _client_ip(_req("10.0.0.1", "1.2.3.4")) == "10.0.0.1"  # header ignored by default
    monkeypatch.setattr(s, "trusted_proxies", "10.0.0.0/8")
    assert _client_ip(_req("10.0.0.1", "1.2.3.4")) == "1.2.3.4"
    assert _client_ip(_req("10.0.0.1", "6.6.6.6, 1.2.3.4, 10.0.0.2")) == "1.2.3.4"  # spoof-safe
    assert _client_ip(_req("8.8.8.8", "1.2.3.4")) == "8.8.8.8"  # untrusted peer
    assert _client_ip(_req("10.0.0.1")) == "10.0.0.1"
