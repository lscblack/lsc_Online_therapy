import subprocess
import sys
import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.deps import current_user, require_role
from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.core.security import (
    TokenExpiredError,
    TokenInvalidError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_secret,
    verify_secret,
)
from app.main import app
from app.models import User
from app.models.user import UserRole
from app.repositories.users import UserRepository
from app.services.identity import IdentityService


def _alembic(*args: str) -> None:
    subprocess.run([sys.executable, "-m", "alembic", *args], check=True)


@pytest.fixture(scope="module", autouse=True)
def schema():
    _alembic("upgrade", "head")
    yield
    _alembic("downgrade", "base")


@pytest.fixture
async def session():
    async with get_sessionmaker()() as s:
        yield s


@pytest.fixture
async def admin(session):
    u = User(anon_id=f"adm-{uuid.uuid4().hex}", role=UserRole.admin,
             email=f"admin-{uuid.uuid4().hex[:8]}@example.org",
             password_hash=hash_secret("s3cret-pass"))
    session.add(u)
    await session.commit()
    return u


@pytest.fixture
async def plain_user(session):
    u = User(anon_id=f"usr-{uuid.uuid4().hex}")
    session.add(u)
    await session.commit()
    return u


@pytest.fixture(scope="module")
def rbac_client():
    probe = FastAPI()
    probe.include_router(app.router)

    @probe.get("/_admin-only")
    async def admin_only(user=Depends(require_role("admin"))):
        return {"id": str(user.id)}

    @probe.get("/_me")
    async def me(user=Depends(current_user)):
        return {"id": str(user.id)}

    return probe


@pytest.fixture
async def rc(rbac_client):
    async with AsyncClient(transport=ASGITransport(app=rbac_client), base_url="http://t") as c:
        yield c


def _bearer(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


async def test_anon_bootstrap_returns_tokens(client):
    r = await client.post("/v1/identity/anon")
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["anon_id"]
    access = decode_token(body["access_token"], expected_type="access")
    refresh = decode_token(body["refresh_token"], expected_type="refresh")
    assert access["role"] == "user" and access["sub"] == refresh["sub"]
    # Refresh yields a new pair
    r2 = await client.post("/v1/identity/refresh", json={"refresh_token": body["refresh_token"]})
    assert r2.status_code == 200
    # An access token must not work as a refresh token
    r3 = await client.post("/v1/identity/refresh", json={"refresh_token": body["access_token"]})
    assert r3.status_code == 401


async def test_upgrade_sets_recovery_and_recover_works(client, session):
    boot = (await client.post("/v1/identity/anon")).json()
    h = _bearer(boot["access_token"])
    # too-short passphrase rejected
    assert (await client.post("/v1/identity/upgrade", headers=h,
                              json={"passphrase": "short"})).status_code == 422
    assert (await client.post("/v1/identity/upgrade",
                              json={"passphrase": "correct horse battery"})).status_code == 401
    r = await client.post("/v1/identity/upgrade", headers=h,
                          json={"passphrase": "correct horse battery"})
    assert r.status_code == 200 and r.json()["is_upgraded"] is True

    user = await UserRepository(session).get_by_anon_id(boot["anon_id"])
    assert user.is_upgraded and user.recovery_hash.startswith("$argon2")
    assert "correct horse" not in user.recovery_hash

    ok = await client.post("/v1/identity/recover", json={
        "anon_id": boot["anon_id"], "passphrase": "correct horse battery"})
    assert ok.status_code == 200
    assert decode_token(ok.json()["access_token"])["sub"] == str(user.id)

    bad = await client.post("/v1/identity/recover", json={
        "anon_id": boot["anon_id"], "passphrase": "wrong passphrase!!"})
    assert bad.status_code == 401
    unknown = await client.post("/v1/identity/recover", json={
        "anon_id": "nope", "passphrase": "correct horse battery"})
    assert unknown.status_code == 401
    assert bad.json() == unknown.json()  # no account enumeration

    # non-upgraded anon account cannot be recovered
    other = (await client.post("/v1/identity/anon")).json()
    r = await client.post("/v1/identity/recover", json={
        "anon_id": other["anon_id"], "passphrase": "correct horse battery"})
    assert r.status_code == 401


async def test_admin_login_and_rbac(rc, session, admin, plain_user):
    svc = IdentityService(session)
    tokens = await svc.login_admin(admin.email, "s3cret-pass")
    assert decode_token(tokens.access_token)["role"] == "admin"

    from app.services.identity import InvalidCredentials
    with pytest.raises(InvalidCredentials):
        await svc.login_admin(admin.email, "wrong")
    with pytest.raises(InvalidCredentials):
        await svc.login_admin("missing@example.org", "s3cret-pass")

    assert (await rc.get("/_admin-only", headers=_bearer(tokens.access_token))).status_code == 200
    user_tok = create_access_token(str(plain_user.id), "user")
    assert (await rc.get("/_admin-only", headers=_bearer(user_tok))).status_code == 403
    assert (await rc.get("/_me", headers=_bearer(user_tok))).status_code == 200
    assert (await rc.get("/_admin-only")).status_code == 401

    # A forged role claim does not escalate: role is read from the DB, not the token.
    forged_role = create_access_token(str(plain_user.id), "admin")
    assert (await rc.get("/_admin-only", headers=_bearer(forged_role))).status_code == 403

    # Disabled user rejected even with a valid token.
    admin.disabled = True
    session.add(admin)
    await session.commit()
    assert (await rc.get("/_admin-only", headers=_bearer(tokens.access_token))).status_code == 401
    with pytest.raises(InvalidCredentials):
        await svc.login_admin(admin.email, "s3cret-pass")


async def test_end_user_cannot_login_as_admin(session, plain_user):
    from app.services.identity import InvalidCredentials
    plain_user.email = f"u-{uuid.uuid4().hex[:6]}@example.org"
    plain_user.password_hash = hash_secret("whatever-pass")
    session.add(plain_user)
    await session.commit()
    with pytest.raises(InvalidCredentials):
        await IdentityService(session).login_admin(plain_user.email, "whatever-pass")


async def test_expired_and_forged_token_rejected(rc, plain_user):
    s = get_settings()
    sub = str(plain_user.id)
    now = datetime.now(UTC)

    def mint(secret=s.jwt_secret, alg="HS256", **over):
        claims = {"sub": sub, "role": "user", "type": "access",
                  "iat": now, "exp": now + timedelta(minutes=5), **over}
        return jwt.encode(claims, secret, algorithm=alg)

    expired = mint(exp=now - timedelta(minutes=1))
    with pytest.raises(TokenExpiredError):
        decode_token(expired)
    assert (await rc.get("/_me", headers=_bearer(expired))).status_code == 401

    wrong_secret = mint(secret="x" * 40)
    with pytest.raises(TokenInvalidError):
        decode_token(wrong_secret)
    assert (await rc.get("/_me", headers=_bearer(wrong_secret))).status_code == 401

    good = create_access_token(sub, "user")
    head, payload, sig = good.split(".")
    tampered = f"{head}.{payload[:-2]}AA.{sig}"
    assert (await rc.get("/_me", headers=_bearer(tampered))).status_code == 401

    # alg=none and a refresh token used as access are both rejected
    none_tok = jwt.encode({"sub": sub, "type": "access", "exp": now + timedelta(minutes=5)},
                          None, algorithm="none")
    assert (await rc.get("/_me", headers=_bearer(none_tok))).status_code == 401
    assert (await rc.get("/_me", headers=_bearer(create_refresh_token(sub)))).status_code == 401
    assert (await rc.get("/_me", headers=_bearer("garbage"))).status_code == 401
    # missing exp is rejected
    no_exp = jwt.encode({"sub": sub, "type": "access"}, s.jwt_secret, algorithm="HS256")
    with pytest.raises(TokenInvalidError):
        decode_token(no_exp)
    # unknown subject
    ghost = create_access_token(str(uuid.uuid4()), "user")
    assert (await rc.get("/_me", headers=_bearer(ghost))).status_code == 401


def test_hash_and_verify_secret():
    h = hash_secret("pw")
    assert h.startswith("$argon2") and verify_secret("pw", h)
    assert not verify_secret("nope", h)
    assert not verify_secret("pw", "not-a-hash")


def test_empty_jwt_secret_fails(monkeypatch):
    from app.core import config
    monkeypatch.setenv("JWT_SECRET", "")
    config.get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError):
            create_access_token("x", "user")
    finally:
        monkeypatch.undo()
        config.get_settings.cache_clear()
