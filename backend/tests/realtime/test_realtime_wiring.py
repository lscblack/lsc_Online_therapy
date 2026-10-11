import asyncio
import sys

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.realtime import reaper
from app.realtime.signaling import SessionRegistry


class FakeEntry:
    def __init__(self, id, identity="u", created=0.0, last=0.0, attached=True, boom=False):
        self.id, self.identity = id, identity
        self.created_at, self.last_activity, self.ws_attached = created, last, attached
        self.boom, self.closed = boom, 0
        self.registry = None

    async def close(self):
        self.closed += 1
        if self.boom:
            raise RuntimeError("teardown exploded")
        if self.registry is not None:
            self.registry.remove(self.id)


def make(*entries):
    reg = SessionRegistry(max_per_identity=100)
    for e in entries:
        reg.add(e)
    return reg


CFG = dict(idle_s=120, max_s=900, attach_grace_s=30)


def test_routes_registered():
    from app.api.v1 import live
    ws_paths = {r.path for r in live.router.routes if r.__class__.__name__ == "APIWebSocketRoute"}
    assert "/v1/live" in ws_paths
    schema = app.openapi()["paths"]
    assert "/v1/live/offer" in schema and "/v1/live/ice" in schema


async def test_idle_session_reaped():
    idle = FakeEntry("a", created=0, last=100)
    fresh = FakeEntry("b", created=0, last=190)
    reg = make(idle, fresh)
    n = await reaper.reap_once(reg, now=300, **CFG)
    assert n == 1 and idle.closed == 1 and fresh.closed == 0
    assert reg.get("a") is None and reg.get("b") is fresh


async def test_session_max_duration_reaped():
    old = FakeEntry("a", created=0, last=999)  # active, but too old
    reg = make(old)
    assert await reaper.reap_once(reg, now=1000, **CFG) == 1
    assert old.closed == 1


async def test_unattached_session_reaped_after_grace():
    waiting = FakeEntry("a", created=100, last=100, attached=False)
    reg = make(waiting)
    assert await reaper.reap_once(reg, now=120, **CFG) == 0  # within grace
    assert await reaper.reap_once(reg, now=131, **CFG) == 1
    assert waiting.closed == 1


async def test_reaper_survives_entry_error():
    bad = FakeEntry("a", last=0, boom=True)
    good = FakeEntry("b", last=0)
    reg = make(bad, good)
    await reaper.reap_once(reg, now=500, **CFG)
    assert good.closed == 1 and bad.closed == 1
    # next pass retries the stuck entry (still registered) without raising
    await reaper.reap_once(reg, now=501, **CFG)
    assert bad.closed == 2


async def test_run_reaper_loop_survives_and_cancels():
    e = FakeEntry("a", last=0)
    reg = make(e)
    calls = {"n": 0}

    def clock():
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("clock broke")  # pass 1 fails
        return 500.0

    t = asyncio.ensure_future(reaper.run_reaper(reg, interval=0.01, clock=clock, **CFG))
    for _ in range(100):
        await asyncio.sleep(0.01)
        if e.closed:
            break
    assert e.closed == 1 and not t.done()
    t.cancel()
    await asyncio.gather(t, return_exceptions=True)
    assert t.cancelled()


def test_app_boots_without_aiortc(monkeypatch):
    monkeypatch.setitem(sys.modules, "aiortc", None)
    monkeypatch.setitem(sys.modules, "av", None)
    from app.core.security import ACCESS, _encode  # noqa: F401
    from app.api.deps import current_user
    from types import SimpleNamespace
    import uuid
    app.dependency_overrides[current_user] = lambda: SimpleNamespace(id=uuid.uuid4())
    try:
        with TestClient(app) as c:
            assert c.get("/v1/health").status_code == 200
            r = c.post("/v1/live/offer", json={"sdp": "v=0", "type": "offer"})
            assert r.status_code == 503
            assert "realtime" in r.text.lower() and "extra" in r.text.lower()
    finally:
        app.dependency_overrides.pop(current_user, None)
