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
    seq = [b"a", b"b", b"gap", b"c", b"gap"]
    events = [e async for e in p.stream(_frames(seq), "rw")]
    assert events == [STTEvent("muraho", True, "rw"), STTEvent("amakuru", True, "rw")]
    assert all(a[:4] == b"RIFF" for a in stt.audios)  # wrapped as WAV for the batch API


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
