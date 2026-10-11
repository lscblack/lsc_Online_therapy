"""WebRTC signaling + control-channel plumbing for realtime voice.

Contracts (see app/api/v1/live.py for the HTTP/WS routes):

* SessionRegistry: in-process, add/get/remove, per-identity cap, enumerate (`all()`),
  `close(id)` / `close_all()` (used by the Task 6 reaper). Entries expose `created_at`,
  `last_activity` (monotonic), `identity`, `live` (LiveSession), `pc`.
* LiveEntry.close(): idempotent teardown -> LiveSession.close(), stop inbound, cancel the feed
  task, close the RTCPeerConnection, then ROLL BACK and CLOSE the session's own DB session
  (a cancel mid-respond() may leave the AsyncSession needing rollback), and unregister.

aiortc is imported lazily (only in `Runtime.new_peer_connection`), so tests inject a fake Runtime.
"""
import asyncio
import contextlib
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from app.core.config import Settings, get_settings
from app.core.db import get_sessionmaker
from app.core.security import ACCESS

logger = logging.getLogger(__name__)


class CapExceeded(Exception):
    pass


@dataclass
class LiveEntry:
    id: str
    identity: str
    live: Any
    pc: Any
    db: Any
    track: Any = None
    inbound: Any = None
    feed_task: asyncio.Task | None = None
    registry: "SessionRegistry | None" = None
    created_at: float = field(default_factory=time.monotonic)
    last_activity: float = field(default_factory=time.monotonic)
    ws_attached: bool = False
    _closing: asyncio.Task | None = field(default=None, repr=False)

    def touch(self) -> None:
        self.last_activity = time.monotonic()

    async def close(self) -> None:
        if self._closing is None:
            self._closing = asyncio.ensure_future(self._do_close())
        await asyncio.shield(self._closing)

    async def _do_close(self) -> None:
        if self.registry is not None:
            self.registry.remove(self.id)
        for step in (self._close_live, self._stop_inbound, self._cancel_feed,
                     self._close_pc, self._close_db):
            try:
                await step()
            except Exception:  # teardown must run to completion
                logger.exception("live session teardown step failed: %s", step.__name__)

    async def _close_live(self) -> None:
        await self.live.close()

    async def _stop_inbound(self) -> None:
        if self.inbound is not None and hasattr(self.inbound, "stop"):
            self.inbound.stop()

    async def _cancel_feed(self) -> None:
        t = self.feed_task
        if t is not None and not t.done() and t is not asyncio.current_task():
            t.cancel()
            await asyncio.gather(t, return_exceptions=True)

    async def _close_pc(self) -> None:
        await self.pc.close()

    async def _close_db(self) -> None:
        try:
            await self.db.rollback()
        finally:
            await self.db.close()


class SessionRegistry:
    def __init__(self, max_per_identity: int | None = None) -> None:
        self._entries: dict[str, LiveEntry] = {}
        self._max = max_per_identity

    @property
    def max_per_identity(self) -> int:
        return self._max if self._max is not None else get_settings().realtime_max_sessions_per_user

    def count(self, identity: str) -> int:
        return sum(1 for e in self._entries.values() if e.identity == identity)

    def at_cap(self, identity: str) -> bool:
        return self.count(identity) >= self.max_per_identity

    def add(self, entry: LiveEntry) -> None:
        """Synchronous (no await between check and insert) so the cap is race-free."""
        if self.at_cap(entry.identity):
            raise CapExceeded(entry.identity)
        entry.registry = self
        self._entries[entry.id] = entry

    def get(self, session_id: str) -> LiveEntry | None:
        return self._entries.get(session_id)

    def remove(self, session_id: str) -> LiveEntry | None:
        return self._entries.pop(session_id, None)

    def all(self) -> list[LiveEntry]:
        return list(self._entries.values())

    def __len__(self) -> int:
        return len(self._entries)

    async def close(self, session_id: str) -> None:
        e = self._entries.get(session_id)
        if e is not None:
            await e.close()

    async def close_all(self) -> None:
        await asyncio.gather(*(e.close() for e in self.all()), return_exceptions=True)


registry = SessionRegistry()


class Runtime:
    """Factory for the heavy/real objects; tests override via FastAPI dependency."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def new_peer_connection(self) -> Any:
        from aiortc import RTCPeerConnection  # lazy
        return RTCPeerConnection()

    def new_tts_track(self) -> Any:
        from app.realtime.media import TtsTrack
        return TtsTrack()

    def new_inbound(self, track: Any) -> Any:
        from app.realtime.media import InboundAudio
        return InboundAudio(track)

    def new_db(self) -> Any:
        return get_sessionmaker()()

    def new_live_session(self, user: Any, language: str, db: Any, *, tts_track: Any,
                         voice: str | None) -> Any:
        from app.realtime.session import LiveSession
        return LiveSession(user, language, db, tts_track=tts_track, voice=voice)

    def session_description(self, sdp: str, type_: str) -> Any:
        from aiortc import RTCSessionDescription
        return RTCSessionDescription(sdp=sdp, type=type_)

    def ice_candidate(self, c: dict) -> Any:
        from aiortc.sdp import candidate_from_sdp
        raw = c["candidate"]
        cand = candidate_from_sdp(raw[len("candidate:"):] if raw.startswith("candidate:") else raw)
        cand.sdpMid = c.get("sdpMid")
        cand.sdpMLineIndex = c.get("sdpMLineIndex")
        return cand

    def ice_servers(self, identity: str) -> list[dict]:
        from app.realtime.turn import get_ice_servers
        return get_ice_servers(self.settings, identity=identity)

    async def ws_user(self, token: str) -> Any:
        """Authenticate a WS token (access JWT). Raises HTTPException(401) if invalid."""
        from app.api.deps import user_from_token
        async with get_sessionmaker()() as s:
            return await user_from_token(token, s, ACCESS)


def get_runtime() -> Runtime:
    return Runtime()


async def create_session(rt: Runtime, user: Any, language: str, voice: str | None,
                         sdp: str, type_: str) -> tuple[LiveEntry, str]:
    """Build PC + tracks + LiveSession, register, negotiate. Caller already authenticated the
    user and checked the cap. Returns (entry, answer_sdp). Tears everything down on failure."""
    identity = str(user.id)
    session_id = uuid.uuid4().hex
    pc = rt.new_peer_connection()
    db = rt.new_db()
    track = rt.new_tts_track()
    live = rt.new_live_session(user, language, db, tts_track=track, voice=voice)
    entry = LiveEntry(id=session_id, identity=identity, live=live, pc=pc, db=db, track=track)
    try:
        registry.add(entry)  # sync; re-checks the cap
    except CapExceeded:
        await entry.close()
        raise

    def on_track(remote: Any) -> None:
        if getattr(remote, "kind", None) != "audio" or entry.inbound is not None:
            return
        entry.inbound = rt.new_inbound(remote)
        entry.feed_task = asyncio.ensure_future(_feed(entry))

    def on_state() -> None:
        if getattr(pc, "connectionState", None) in ("failed", "closed"):
            asyncio.ensure_future(entry.close())

    pc.on("track", on_track)
    pc.on("connectionstatechange", on_state)
    try:
        pc.addTrack(track)
        await pc.setRemoteDescription(rt.session_description(sdp, type_))
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)
        local = pc.localDescription
        return entry, local.sdp
    except BaseException:
        await entry.close()
        raise


async def _feed(entry: LiveEntry) -> None:
    try:
        await entry.live.feed(entry.inbound.frames())
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("live feed failed")
    finally:
        entry.touch()
