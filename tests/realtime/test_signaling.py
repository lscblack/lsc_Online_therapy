import asyncio
import uuid
from datetime import timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.deps import current_user
from app.core.security import ACCESS, _encode
from app.main import app
from app.realtime import signaling
from app.realtime.signaling import Runtime, get_runtime


class FakePC:
    def __init__(self, log):
        self.handlers = {}
        self.closed = False
        self.tracks = []
        self.ice = []
        self.localDescription = None
        log.append(self)

    def on(self, ev, fn=None):
        self.handlers[ev] = fn

    def addTrack(self, t):
        self.tracks.append(t)

    async def setRemoteDescription(self, d):
        self.remote = d

    async def createAnswer(self):
        return SimpleNamespace(sdp="ANSWER", type="answer")

    async def setLocalDescription(self, d):
        self.localDescription = d

    async def addIceCandidate(self, c):
        self.ice.append(c)

    async def close(self):
        self.closed = True


class FakeDB:
    def __init__(self):
        self.rolled_back = self.closed = False

    async def rollback(self):
        self.rolled_back = True

    async def close(self):
        assert self.rolled_back  # rollback precedes close
        self.closed = True


class FakeLive:
    def __init__(self, script=()):
        self.q = asyncio.Queue()
        for e in script:
            self.q.put_nowait(e)
        self.closed = False
        self.barged = 0

    async def events(self):
        while True:
            e = await self.q.get()
            if e is None:
                return
            yield e

    async def feed(self, frames):
        await asyncio.sleep(3600)

    async def barge_in(self):
        self.barged += 1

    async def close(self):
        self.closed = True
        self.q.put_nowait(None)


class FakeRuntime(Runtime):
    def __init__(self, script=()):
        self.pcs, self.dbs, self.lives = [], [], []
        self.script = script

    def new_peer_connection(self):
        return FakePC(self.pcs)

    def new_tts_track(self):
        return object()

    def new_inbound(self, track):
        return SimpleNamespace(frames=lambda: None, stop=lambda: None)

    def new_db(self):
        d = FakeDB()
        self.dbs.append(d)
        return d

    def new_live_session(self, user, language, db, *, tts_track, voice):
        l = FakeLive(self.script)
        self.lives.append(l)
        return l

    def session_description(self, sdp, type_):
        return SimpleNamespace(sdp=sdp, type=type_)

    def ice_candidate(self, c):
        return c

    def ice_servers(self, identity):
        return [{"urls": ["stun:x"]}]

    async def ws_user(self, token):
        return USER if token == "good" else (_ for _ in ()).throw(
            __import__("fastapi").HTTPException(401))


USER = SimpleNamespace(id=uuid.uuid4())


@pytest.fixture
def rt():
    r = FakeRuntime(script=[{"type": "state", "state": "listening"},
                            {"type": "transcript_partial", "text": "hel"}])
    signaling.registry._entries.clear()
    signaling.registry._max = 2
    app.dependency_overrides[get_runtime] = lambda: r
    yield r
    app.dependency_overrides.clear()
    signaling.registry._entries.clear()
    signaling.registry._max = None


@pytest.fixture
def authed():
    app.dependency_overrides[current_user] = lambda: USER


BODY = {"sdp": "OFFER", "type": "offer", "language": "en"}


def test_offer_requires_auth(rt):
    with TestClient(app) as c:
        assert c.post("/v1/live/offer", json=BODY).status_code == 401
        assert c.post("/v1/live/offer", json=BODY,
                      headers={"Authorization": "Bearer garbage"}).status_code == 401
        expired = _encode(str(uuid.uuid4()), ACCESS, timedelta(seconds=-10), {"role": "user"})
        assert c.post("/v1/live/offer", json=BODY,
                      headers={"Authorization": f"Bearer {expired}"}).status_code == 401
    assert rt.pcs == []
    assert len(signaling.registry) == 0


def test_offer_returns_answer_and_registers(rt, authed):
    with TestClient(app) as c:
        r = c.post("/v1/live/offer", json=BODY)
        assert r.status_code == 200
        j = r.json()
        assert j["sdp"] == "ANSWER" and j["type"] == "answer"
        assert j["ice_servers"] == [{"urls": ["stun:x"]}]
        assert signaling.registry.get(j["session_id"]) is not None
        assert len(rt.pcs) == 1 and rt.pcs[0].tracks
        r2 = c.post("/v1/live/ice", json={"session_id": j["session_id"],
                                          "candidate": {"candidate": "c"}})
        assert r2.status_code == 204 and rt.pcs[0].ice == [{"candidate": "c"}]
        assert c.post("/v1/live/ice", json={"session_id": "nope"}).status_code == 404


def test_offer_over_cap_refused(rt, authed):
    with TestClient(app) as c:
        assert c.post("/v1/live/offer", json=BODY).status_code == 200
        assert c.post("/v1/live/offer", json=BODY).status_code == 200
        r = c.post("/v1/live/offer", json=BODY)
        assert r.status_code == 429
    assert len(rt.pcs) == 2  # no third PC


def test_control_ws_streams_session_events(rt, authed):
    with TestClient(app) as c:
        j = c.post("/v1/live/offer", json=BODY).json()
        sid = j["session_id"]
        with c.websocket_connect(f"/v1/live?session_id={sid}&ticket={j['ws_ticket']}") as ws:
            assert ws.receive_json() == {"type": "state", "state": "listening"}
            assert ws.receive_json() == {"type": "transcript_partial", "text": "hel"}
            ws.send_json({"type": "barge_in"})
            ws.send_json({"type": "end"})
        assert rt.lives[0].barged == 1


def _ws_close_code(c, url):
    """Connect must SUCCEED (socket accepted) and then deliver the app close code; a pre-accept
    close would be an HTTP 403 handshake rejection and the context would raise instead."""
    with c.websocket_connect(url) as ws:
        msg = ws.receive()
        assert msg["type"] == "websocket.close"
        return msg["code"]


def test_ws_close_codes_delivered_after_accept(rt, authed):
    with TestClient(app) as c:
        j = c.post("/v1/live/offer", json=BODY).json()
        sid, tk = j["session_id"], j["ws_ticket"]
        assert _ws_close_code(c, f"/v1/live?session_id={sid}&ticket=bad") == 4401
        assert _ws_close_code(c, f"/v1/live?session_id={sid}") == 4401
        assert _ws_close_code(c, "/v1/live?session_id=nope&ticket=x") == 4401
        # valid bearer header but unknown session -> 4404
        with c.websocket_connect("/v1/live?session_id=nope",
                                 headers={"Authorization": "Bearer good"}) as ws:
            assert ws.receive()["code"] == 4404
        # a ticket for session A is rejected for B (and burned); and is single-use
        j2 = c.post("/v1/live/offer", json=BODY).json()
        assert _ws_close_code(c, f"/v1/live?session_id={j2['session_id']}&ticket={tk}") == 4401
        assert _ws_close_code(c, f"/v1/live?session_id={sid}&ticket={tk}") == 4401
        tk = signaling.issue_ticket(sid, str(USER.id))
        with c.websocket_connect(f"/v1/live?session_id={sid}&ticket={tk}") as ws:
            ws.receive_json()
        assert _ws_close_code(c, f"/v1/live?session_id={sid}&ticket={tk}") == 4401


def test_ws_already_attached_4409(rt, authed):
    with TestClient(app) as c:
        j = c.post("/v1/live/offer", json=BODY).json()
        sid = j["session_id"]
        with c.websocket_connect(f"/v1/live?session_id={sid}&ticket={j['ws_ticket']}") as ws:
            ws.receive_json()
            with c.websocket_connect(f"/v1/live?session_id={sid}",
                                     headers={"Authorization": "Bearer good"}) as ws2:
                assert ws2.receive()["code"] == 4409
            assert not rt.lives[0].closed  # the intruder does not tear down the owner
            ws.send_json({"type": "end"})


def test_cap_slot_released_after_teardown(rt, authed):
    with TestClient(app) as c:
        ids = [c.post("/v1/live/offer", json=BODY).json()["session_id"] for _ in range(2)]
        assert c.post("/v1/live/offer", json=BODY).status_code == 429
        e = signaling.registry.get(ids[0])
        c.portal.call(e.close)
        assert c.post("/v1/live/offer", json=BODY).status_code == 200


def test_construction_failure_cleans_up_pc_and_db(rt, authed):
    def boom(*a, **k):
        raise RuntimeError("x")
    rt.new_tts_track = boom
    with TestClient(app, raise_server_exceptions=False) as c:
        assert c.post("/v1/live/offer", json=BODY).status_code == 500
    assert rt.pcs[0].closed
    assert rt.dbs[0].rolled_back and rt.dbs[0].closed
    assert len(signaling.registry) == 0


def test_internal_error_is_500_not_400(rt, authed):
    async def boom(self, d):
        raise RuntimeError("internal")
    FakePC.setRemoteDescription, orig = boom, FakePC.setRemoteDescription
    try:
        with TestClient(app, raise_server_exceptions=False) as c:
            assert c.post("/v1/live/offer", json=BODY).status_code == 500
    finally:
        FakePC.setRemoteDescription = orig
    assert rt.pcs[0].closed and len(signaling.registry) == 0


def test_connection_failed_closes_session(rt, authed):
    with TestClient(app) as c:
        sid = c.post("/v1/live/offer", json=BODY).json()["session_id"]
        e = signaling.registry.get(sid)
        pc = rt.pcs[0]
        pc.connectionState = "failed"

        async def fire():
            pc.handlers["connectionstatechange"]()
            while e._closing is None:
                await asyncio.sleep(0.01)
            await asyncio.wait_for(asyncio.shield(e._closing), 2)
        c.portal.call(fire)
        assert rt.lives[0].closed and signaling.registry.get(sid) is None


@pytest.mark.parametrize("how", ["end", "drop"])
def test_disconnect_closes_session(rt, authed, how):
    with TestClient(app) as c:
        j = c.post("/v1/live/offer", json=BODY).json()
        sid = j["session_id"]
        entry = signaling.registry.get(sid)
        with c.websocket_connect(f"/v1/live?session_id={sid}&ticket={j['ws_ticket']}") as ws:
            ws.receive_json()
            if how == "end":
                ws.send_json({"type": "end"})
        # socket dropped on exit; wait deterministically for the teardown task itself

        async def wait_closed():
            while entry._closing is None:
                await asyncio.sleep(0.01)
            await asyncio.wait_for(asyncio.shield(entry._closing), 5)
        c.portal.call(wait_closed)
    assert entry.errors == []  # no swallowed teardown failure
    assert rt.lives[0].closed
    assert rt.pcs[0].closed
    assert rt.dbs[0].rolled_back and rt.dbs[0].closed
    assert signaling.registry.get(sid) is None


def test_non_terminal_connection_state_is_noop(rt, authed):
    with TestClient(app) as c:
        sid = c.post("/v1/live/offer", json=BODY).json()["session_id"]
        e = signaling.registry.get(sid)
        pc = rt.pcs[0]

        async def fire():
            before = len(signaling._bg)
            for st in ("new", "connecting", "connected"):
                pc.connectionState = st
                pc.handlers["connectionstatechange"]()  # must not raise
            await asyncio.sleep(0.05)
            assert len(signaling._bg) == before
            assert e._closing is None
        c.portal.call(fire)
        assert not rt.lives[0].closed and signaling.registry.get(sid) is e
