import pytest

from app.core.config import Settings
from app.providers import factory
from app.providers.factory import ProviderConfigError
from app.providers.fakes import FakeSTT
from app.providers.streaming_stt import (
    FakeStreamingSTT, StreamingVendorSTT, STTEvent, VadSegmentedSTT,
)
from app.realtime.vad import VadEvent


def _s(**kw):
    base = dict(database_url="postgresql+asyncpg://x/y_test", openrouter_api_key="k",
                llm_model="m/x", stt_provider="fake")
    base.update(kw)
    return Settings(_env_file=None, **base)


def test_factory_selects_vad_segmented_for_kinyarwanda():
    s = _s(streaming_stt_api_key="dg")
    assert isinstance(factory.get_streaming_stt("rw", s), VadSegmentedSTT)
    assert isinstance(factory.get_streaming_stt("kin", s), VadSegmentedSTT)
    assert isinstance(factory.get_streaming_stt(None, s), VadSegmentedSTT)


def test_factory_selects_streaming_for_english():
    s = _s(streaming_stt_api_key="dg")
    assert isinstance(factory.get_streaming_stt("en-US", s), StreamingVendorSTT)


def test_factory_english_falls_back_to_vad_when_vendor_unconfigured():
    assert isinstance(factory.get_streaming_stt("en", _s()), VadSegmentedSTT)


def test_factory_explicit_vendor_unconfigured_raises():
    with pytest.raises(ProviderConfigError):
        factory.get_streaming_stt("en", _s(streaming_stt_provider="deepgram"))
    with pytest.raises(ProviderConfigError):
        factory.get_streaming_stt("en", _s(streaming_stt_provider="nope"))


def test_factory_fake_and_vad_overrides():
    assert isinstance(factory.get_streaming_stt("en", _s(streaming_stt_provider="fake")),
                      FakeStreamingSTT)
    s = _s(streaming_stt_provider="vad", streaming_stt_api_key="dg")
    assert isinstance(factory.get_streaming_stt("en", s), VadSegmentedSTT)


class ScriptedVad:
    """Marks utterances at fixed frame positions; audio is the frames joined."""

    def __init__(self):
        self.calls = 0

    async def __call__(self, frames):
        buf: list[bytes] = []
        async for f in frames:
            if f == b"gap":
                if buf:
                    yield VadEvent("speech_start")
                    yield VadEvent("speech_end", audio=b"".join(buf))
                    buf = []
            else:
                buf.append(f)


class SeqSTT:
    def __init__(self, texts):
        self.texts, self.audios = list(texts), []

    async def transcribe(self, audio, language, filename=None):
        self.audios.append(audio)
        from app.providers.base import Transcript
        return Transcript(text=self.texts.pop(0), language=language)


async def _frames(seq):
    for f in seq:
        yield f


async def test_vad_segmented_emits_final_per_utterance():
    stt = SeqSTT(["muraho", "amakuru"])
    p = VadSegmentedSTT(stt, ScriptedVad())
    seq = [b"aa", b"bb", b"gap", b"cc", b"gap"]
    events = [e async for e in p.stream(_frames(seq), "rw")]
    assert events == [STTEvent("muraho", True, "rw"), STTEvent("amakuru", True, "rw")]
    import io, wave
    pcm = []
    for a in stt.audios:
        assert a[:4] == b"RIFF"  # wrapped as WAV for the batch API
        with wave.open(io.BytesIO(a)) as w:
            pcm.append(w.readframes(w.getnframes()))
    assert pcm == [b"aabb", b"cc"]  # exact content: nothing dropped or duplicated


async def test_vad_segmented_skips_empty_transcripts():
    p = VadSegmentedSTT(SeqSTT(["  "]), ScriptedVad())
    assert [e async for e in p.stream(_frames([b"a", b"gap"]), "en")] == []


async def test_fake_streaming_scripted():
    ev = [STTEvent("hel", False, "en"), STTEvent("hello", True, "en")]
    f = FakeStreamingSTT(ev)
    assert [e async for e in f.stream(_frames([b"x"]), "en")] == ev


def test_vendor_requires_key():
    with pytest.raises(ProviderConfigError):
        StreamingVendorSTT(api_key="", model="nova-2", url="wss://x")
    assert FakeSTT  # imported for parity


def test_factory_unrecognised_language_routes_to_vad():
    assert isinstance(factory.get_streaming_stt("fr", _s(streaming_stt_api_key="dg")),
                      VadSegmentedSTT)


async def test_real_segmenter_with_vad_segmented_stt_end_to_end():
    import functools
    import struct
    from app.realtime import vad
    loud = struct.pack("<320h", *([8000, -8000] * 160))
    quiet = b"\x00\x00" * 320
    seg = functools.partial(vad.segment, backend=vad.EnergyBackend(500), frame_ms=20,
                            silence_ms=60, min_speech_ms=40)
    stt = SeqSTT(["one", "two"])
    p = VadSegmentedSTT(stt, seg)
    seq = [quiet] + [loud] * 4 + [quiet] * 4 + [loud] * 3 + [quiet] * 4
    events = [e async for e in p.stream(_frames(seq), "en")]
    assert [e.text for e in events] == ["one", "two"]


async def test_vad_segmented_closes_upstream_on_early_exit():
    closed = []

    async def src():
        try:
            for _ in range(1000):
                yield b"a"
                yield b"gap"
        finally:
            closed.append("frames")

    p = VadSegmentedSTT(SeqSTT(["x"] * 5), ScriptedVad())
    g = p.stream(src(), "en")
    async for _ in g:
        break
    await g.aclose()
    assert "frames" in closed


class _FakeWS:
    def __init__(self, fail_send=False):
        self.fail_send, self.sent, self.closed = fail_send, [], False
        self._q = __import__("asyncio").Queue()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def send(self, d):
        if self.fail_send:
            raise RuntimeError("boom")
        self.sent.append(d)

    async def close(self):
        self.closed = True
        await self._q.put(None)

    def __aiter__(self):
        return self

    async def __anext__(self):
        m = await self._q.get()
        if m is None:
            raise StopAsyncIteration
        return m


async def test_vendor_pump_failure_surfaced_and_no_leaked_task(monkeypatch):
    import asyncio
    import websockets
    from app.providers.base import ProviderError
    ws = _FakeWS(fail_send=True)
    monkeypatch.setattr(websockets, "connect", lambda *a, **k: ws)
    closed = []

    async def src():
        try:
            yield b"x"
            await asyncio.sleep(10)
        finally:
            closed.append(1)

    v = StreamingVendorSTT("k", "m", "wss://x")
    with pytest.raises(ProviderError):
        async for _ in v.stream(src(), "en"):
            pass
    assert closed == [1]
    assert [t for t in asyncio.all_tasks() if "stream.<locals>.pump" in t.get_coro().__qualname__] == []


async def test_vendor_early_exit_cancels_pump_and_closes_frames(monkeypatch):
    import asyncio
    import json
    import websockets
    ws = _FakeWS()
    await ws._q.put(json.dumps({"is_final": True, "channel": {"alternatives": [{"transcript": "hi"}]}}))
    monkeypatch.setattr(websockets, "connect", lambda *a, **k: ws)
    closed = []

    async def src():
        try:
            while True:
                yield b"x"
                await asyncio.sleep(0.01)
        finally:
            closed.append(1)

    g = StreamingVendorSTT("k", "m", "wss://x").stream(src(), "en")
    ev = await g.__anext__()
    assert ev.text == "hi" and ev.is_final
    await asyncio.sleep(0.05)  # let the pump start consuming frames
    await g.aclose()
    assert closed == [1]
    assert [t for t in asyncio.all_tasks() if "stream.<locals>.pump" in t.get_coro().__qualname__] == []


async def test_vendor_rejects_unsupported_language():
    v = StreamingVendorSTT("k", "m", "wss://x")
    with pytest.raises(ProviderConfigError):
        async for _ in v.stream(_frames([b"x"]), "rw"):
            pass
