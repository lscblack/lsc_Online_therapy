import asyncio
import uuid

import pytest
from sqlalchemy import delete

from app.core.config import get_settings
from app.core.db import get_engine, get_sessionmaker
from app.core.i18n import t
from app.models import Document, User
from app.providers.fakes import FakeLLM, FakeTTS
from app.providers.streaming_stt import STTEvent
from app.realtime.session import LiveSession, State
from app.services.chat import ChatService
from tests.rag.test_retrieval import T_FP, _doc
from tests.test_identity import schema as _schema  # noqa: F401

SPEECH = b"S" * 640
SILENCE = b"\x00" * 640


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
    u = User(anon_id=f"live-{uuid.uuid4().hex}")
    session.add(u)
    await session.commit()
    return u


class FakeVad:
    def is_speech(self, frame: bytes) -> bool:
        return frame == SPEECH


class ControlledSTT:
    """Emits events pushed by the test; drains the frame iterator in the background."""

    def __init__(self):
        self.q: asyncio.Queue = asyncio.Queue()
        self.frames = 0
        self.closed = False

    async def stream(self, frames, language):
        async def drain():
            async for _ in frames:
                self.frames += 1

        d = asyncio.ensure_future(drain())
        try:
            while True:
                ev = await self.q.get()
                if ev is None:
                    return
                yield ev
        finally:
            self.closed = True
            d.cancel()


class FakeTrack:
    def __init__(self):
        self.played: list = []
        self.cancels = 0
        self.stopped = False
        self.playing = False

    @property
    def is_playing(self):
        return self.playing

    def play(self, chunks):
        self.played.append(chunks)
        self.playing = True

    def cancel(self):
        self.cancels += 1
        self.playing = False

    def stop(self):
        self.stopped = True


class FakeInbound:
    def __init__(self):
        self.stopped = False

    def stop(self):
        self.stopped = True


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


async def until(cond, timeout=2.0):
    end = asyncio.get_running_loop().time() + timeout
    while not cond():
        assert asyncio.get_running_loop().time() < end, "timeout"
        await asyncio.sleep(0.005)


class Harness:
    def __init__(self, session, user, llm, **kw):
        self.stt = ControlledSTT()
        self.track = FakeTrack()
        self.inbound = FakeInbound()
        self.clock = Clock()
        self.frames: asyncio.Queue = asyncio.Queue()
        self.events: list[dict] = []
        kw.setdefault("barge_in_grace_ms", 0)
        kw.setdefault("barge_in_min_speech_ms", 40)
        kw.setdefault("crisis_min_play_ms", 3000)
        self.live = LiveSession(
            user, "en", session, chat=ChatService(session, llm=llm), stt=self.stt, tts=FakeTTS(),
            tts_track=self.track, vad=FakeVad(), inbound=self.inbound, clock=self.clock,
            playback_poll_s=0.005, **kw)

    async def start(self):
        async def gen():
            while True:
                f = await self.frames.get()
                if f is None:
                    return
                yield f

        self._collect = asyncio.ensure_future(self._collector())
        self.feed_task = asyncio.ensure_future(self.live.feed(gen()))
        await until(lambda: self.live.state == State.LISTENING)

    async def _collector(self):
        async for e in self.live.events():
            self.events.append(e)

    def types(self):
        return [e["type"] for e in self.events]

    async def say(self, text):
        await self.stt.q.put(STTEvent(text, True, "en"))

    async def finish(self):
        await self.live.close()
        await self._collect
        self.feed_task.cancel()
        await asyncio.gather(self.feed_task, return_exceptions=True)


def spoken(track):
    return [p for p in track.played]


async def test_utterance_goes_through_chatservice_and_speaks_guarded_answer(session, user):
    await _doc(session, "FP Guide", [T_FP])
    llm = FakeLLM(["Condoms and pills are common methods ", "[S1]."])
    h = Harness(session, user, llm)
    await h.start()
    await h.stt.q.put(STTEvent("Condoms", False, "en"))
    await h.say(T_FP)
    await until(lambda: h.track.played)
    expected = (await FakeTTS().synthesize("Condoms and pills are common methods.", "en", None))
    assert h.track.played == [expected]  # markers stripped; exactly the guarded answer
    assert len(llm.calls) >= 1
    assert h.live.state == State.SPEAKING
    h.track.playing = False
    await until(lambda: h.live.state == State.LISTENING)
    await until(lambda: len(h.events) >= 9)
    ty = h.types()
    assert "transcript_partial" in ty and "transcript_final" in ty
    assert ty.index("transcript_final") < ty.index("answer")
    cit = next(e for e in h.events if e["type"] == "citations")
    assert cit["citations"][0]["id"] == "S1"
    assert any(e["type"] == "safety_flags" for e in h.events)
    states = [e["state"] for e in h.events if e["type"] == "state"]
    assert states[:4] == ["listening", "thinking", "speaking", "listening"]
    await h.finish()


async def test_no_audio_before_guarded_result(session, user, monkeypatch):
    h = Harness(session, user, FakeLLM(["x"]))
    gate = asyncio.Event()
    orig = h.live._chat.respond

    async def slow(*a, **k):
        assert not h.track.played
        await gate.wait()
        return await orig(*a, **k)

    monkeypatch.setattr(h.live._chat, "respond", slow)
    await h.start()
    await h.say("how are you")
    await until(lambda: h.live.state == State.THINKING)
    await asyncio.sleep(0.05)
    assert h.track.played == []
    gate.set()
    await until(lambda: h.track.played)
    await h.finish()


async def test_crisis_utterance_bypasses_rag_and_speaks_referral(session, user, monkeypatch):
    import app.services.chat as chat_mod

    async def boom(*a, **k):
        raise AssertionError("retrieval must not run for crisis")

    monkeypatch.setattr(chat_mod, "retrieve", boom)
    llm = FakeLLM(["MODEL ANSWER MUST NOT APPEAR"])
    h = Harness(session, user, llm)
    await h.start()
    await h.say("I want to kill myself")
    await until(lambda: h.track.played)
    text = h.track.played[0].decode()
    assert t("crisis_self_harm", "en") in text
    assert "MODEL ANSWER" not in text and llm.calls == []
    await until(lambda: "safety_flags" in h.types())
    flags = next(e for e in h.events if e["type"] == "safety_flags")
    assert flags["safety_flags"]["crisis"] is True
    await h.finish()


async def _speaking(h, text="hello there"):
    await h.say(text)
    await until(lambda: h.live.state == State.SPEAKING)


async def test_barge_in_cancels_inflight_tts_and_generation(session, user):
    await _doc(session, "FP Guide", [T_FP])
    h = Harness(session, user, FakeLLM(["Condoms and pills ", "[S1]."]))
    await h.start()
    await _speaking(h, T_FP)
    turn = h.live._turn
    for _ in range(3):
        await h.frames.put(SPEECH)
    await until(lambda: h.live.state == State.LISTENING)
    assert h.track.cancels >= 1
    assert turn.cancelled()  # generation/speech task was cancelled
    assert "barge_in" in h.types()
    # the new utterance proceeds normally
    await h.say("and another question")
    await until(lambda: len(h.track.played) == 2)
    await h.finish()


async def test_barge_in_cancels_generation_task(session, user, monkeypatch):
    h = Harness(session, user, FakeLLM(["x"]))
    started = asyncio.Event()
    cancelled = []

    async def hang(*a, **k):
        started.set()
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            cancelled.append(True)
            raise

    monkeypatch.setattr(h.live._chat, "respond", hang)
    await h.start()
    await h.say("question")
    await started.wait()
    await h.say("actually, different question")  # new final while thinking supersedes
    await until(lambda: len(cancelled) >= 1)
    await h.finish()


async def test_grace_period_ignores_early_speech(session, user):
    h = Harness(session, user, FakeLLM(["Hello there friend."]), barge_in_grace_ms=500)
    await h.start()
    await _speaking(h)
    for _ in range(5):
        await h.frames.put(SPEECH)
    await until(lambda: h.stt.frames >= 5)
    assert h.track.cancels == 0 and h.live.state == State.SPEAKING
    h.clock.now += 1.0
    for _ in range(3):
        await h.frames.put(SPEECH)
    await until(lambda: h.live.state == State.LISTENING)
    await h.finish()


async def test_barge_in_during_crisis_keeps_referral_line(session, user):
    h = Harness(session, user, FakeLLM(["no"]))
    await h.start()
    await _speaking(h, "I want to kill myself")
    for _ in range(5):
        await h.frames.put(SPEECH)
    await until(lambda: h.stt.frames >= 5)
    assert h.track.cancels == 0 and h.live.state == State.SPEAKING  # mandatory line protected
    assert "barge_in" not in h.types()
    h.clock.now += 3.5  # mandatory window elapsed
    for _ in range(3):
        await h.frames.put(SPEECH)
    await until(lambda: h.live.state == State.LISTENING)
    assert h.track.cancels == 1 and "barge_in" in h.types()
    await h.finish()


async def test_new_final_during_crisis_waits_for_mandatory_line(session, user):
    h = Harness(session, user, FakeLLM(["Hi again, friend."]))
    await h.start()
    await _speaking(h, "I want to kill myself")
    await h.say("hello")  # arrives immediately
    await asyncio.sleep(0.05)
    assert h.track.cancels == 0 and len(h.track.played) == 1
    h.clock.now += 3.5
    await until(lambda: len(h.track.played) == 2)  # waited, then superseded
    assert h.track.cancels == 1
    await h.finish()


async def test_close_tears_down_everything(session, user):
    before = asyncio.all_tasks()
    h = Harness(session, user, FakeLLM(["Hello there friend."]))
    await h.start()
    await _speaking(h)
    refs = list(h.live._tasks)
    assert refs
    await h.live.close()
    await h.live.close()  # idempotent
    assert all(r.done() for r in refs)
    assert h.stt.closed and h.inbound.stopped and h.track.stopped and h.track.cancels >= 1
    assert h.live.state == State.IDLE
    await h._collect
    await asyncio.wait_for(h.feed_task, 1)  # feed returns after close
    leaked = [x for x in asyncio.all_tasks() - before
              if not x.done() and x is not asyncio.current_task()]
    assert leaked == []


async def test_conversation_id_continuity(session, user):
    h = Harness(session, user, FakeLLM(["Hello there friend."]))
    await h.start()
    await h.say("first")
    await until(lambda: h.track.played)
    h.track.playing = False
    await until(lambda: h.live.state == State.LISTENING)
    cid = h.live.conversation_id
    assert cid is not None
    await h.say("second")
    await until(lambda: len(h.track.played) == 2)
    assert h.live.conversation_id == cid
    answers = [e for e in h.events if e["type"] == "answer"]
    assert {e["conversation_id"] for e in answers} == {str(cid)}
    await h.finish()
