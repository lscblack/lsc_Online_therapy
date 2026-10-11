import struct

from app.realtime import vad
from app.realtime.vad import EnergyBackend, VadEvent, VadSegmenter

LOUD = struct.pack("<320h", *([8000, -8000] * 160))  # 20ms @16k
QUIET = b"\x00\x00" * 320


class ScriptedBackend:
    def is_speech(self, frame: bytes) -> bool:
        return frame == LOUD


async def _frames(seq):
    for f in seq:
        yield f


def test_is_speech_loud_vs_silent():
    b = EnergyBackend(threshold=500)
    assert vad.is_speech(LOUD, backend=b) is True
    assert vad.is_speech(QUIET, backend=b) is False


async def test_endpointing_speech_start_then_end_after_silence():
    # 10 speech frames (200ms), 5 silence frames (100ms) -> end at silence_ms=100
    seq = [QUIET] * 2 + [LOUD] * 10 + [QUIET] * 5 + [QUIET] * 3
    events = [e async for e in vad.segment(
        _frames(seq), backend=ScriptedBackend(), frame_ms=20, silence_ms=100, min_speech_ms=60)]
    assert [e.type for e in events] == ["speech_start", "speech_end"]
    end = events[1]
    assert isinstance(end, VadEvent)
    assert LOUD * 10 in end.audio


async def test_short_burst_ignored_and_open_utterance_flushed():
    seq = [LOUD] * 2 + [QUIET] * 10  # 40ms burst < min_speech 100ms
    events = [e async for e in vad.segment(
        _frames(seq), backend=ScriptedBackend(), frame_ms=20, silence_ms=100, min_speech_ms=100)]
    assert events == []
    seq = [LOUD] * 10  # stream ends mid-speech -> flushed
    events = [e async for e in vad.segment(
        _frames(seq), backend=ScriptedBackend(), frame_ms=20, silence_ms=100, min_speech_ms=100)]
    assert [e.type for e in events] == ["speech_start", "speech_end"]


def test_segmenter_two_utterances():
    s = VadSegmenter(ScriptedBackend(), frame_ms=20, silence_ms=40, min_speech_ms=40)
    out = []
    for f in [LOUD] * 3 + [QUIET] * 2 + [LOUD] * 3 + [QUIET] * 2:
        out += s.feed(f)
    assert [e.type for e in out] == ["speech_start", "speech_end"] * 2
