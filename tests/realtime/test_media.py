import array
import asyncio
from dataclasses import dataclass

import pytest

from app.realtime.media import (
    InboundAudio,
    Pcm16Resampler,
    TtsTrack,
    pcm_from_frame,
)

pytestmark = pytest.mark.asyncio

FRAME48 = 960 * 2  # 20 ms @ 48 kHz mono s16 = 1920 bytes
FRAME16 = 320 * 2  # 20 ms @ 16 kHz mono s16 = 640 bytes


@dataclass
class FakeOut:
    pcm: bytes
    pts: int
    sample_rate: int


def make_track(**kw):
    return TtsTrack(
        frame_factory=lambda pcm, pts, rate: FakeOut(pcm, pts, rate),
        pace=False,
        input_format="pcm16",
        input_rate=48000,
        **kw,
    )


def pcm(value: int, n_frames: int = 1) -> bytes:
    return array.array("h", [value] * (960 * n_frames)).tobytes()


async def settle():
    for _ in range(5):
        await asyncio.sleep(0)


async def test_tts_track_emits_fed_chunks():
    t = make_track()
    t.play(pcm(100, 2) + pcm(200, 1))
    await settle()
    outs = [await t.recv() for _ in range(3)]
    assert [o.pcm for o in outs] == [pcm(100), pcm(100), pcm(200)]
    assert [o.pts for o in outs] == [0, 960, 1920]
    assert all(o.sample_rate == 48000 for o in outs)
    # then silence
    o = await t.recv()
    assert o.pcm == bytes(FRAME48) and o.pts == 2880


async def test_tts_track_streams_async_iterator_with_odd_chunks():
    t = make_track()
    data = pcm(7, 2)

    async def gen():
        for i in range(0, len(data), 1000):
            yield data[i : i + 1000]
            await asyncio.sleep(0)

    t.play(gen())
    await asyncio.sleep(0.01)
    assert t.is_playing
    got = b"".join([(await t.recv()).pcm for _ in range(2)])
    assert got == data


async def test_tts_track_cancel_stops_output_promptly():
    t = make_track()
    gate = asyncio.Event()

    async def gen():
        yield pcm(5, 10)
        await gate.wait()  # producer still streaming
        yield pcm(5, 10)

    t.play(gen())
    await settle()
    assert t.is_playing
    assert (await t.recv()).pcm == pcm(5)
    t.cancel()
    assert not t.is_playing
    for _ in range(3):
        assert (await t.recv()).pcm == bytes(FRAME48)
    gate.set()
    await settle()
    assert (await t.recv()).pcm == bytes(FRAME48)
    assert t._feeder is None or t._feeder.done()
    assert not t.is_playing


async def test_tts_track_cancel_then_play_again():
    t = make_track()
    t.play(pcm(1, 5))
    await settle()
    await t.recv()
    t.cancel()
    assert (await t.recv()).pcm == bytes(FRAME48)
    t.play(pcm(9, 1))
    await settle()
    assert t.is_playing
    assert (await t.recv()).pcm == pcm(9)
    assert (await t.recv()).pcm == bytes(FRAME48)
    assert not t.is_playing


async def test_tts_track_decodes_encoded_bytes_via_injected_decoder():
    seen = []

    def decoder(data: bytes) -> bytes:
        seen.append(data)
        return pcm(3, 1)

    t = TtsTrack(
        frame_factory=lambda p, pts, r: FakeOut(p, pts, r),
        pace=False,
        decoder=decoder,
    )
    t.play(b"mp3-a")

    async def gen():
        yield b"mp3-"
        yield b"b"

    t.play(gen())
    await asyncio.sleep(0.01)
    assert seen == [b"mp3-a", b"mp3-b"]
    assert (await t.recv()).pcm == pcm(3)
    assert (await t.recv()).pcm == pcm(3)


@dataclass
class FakeLayout:
    channels: int


class FakeFormat:
    name = "s16"


class FakeFrame:
    def __init__(self, samples, rate=48000, channels=1):
        self.sample_rate = rate
        self.layout = FakeLayout(channels)
        self.format = FakeFormat()
        self.samples = len(samples) // channels
        self.planes = [array.array("h", samples).tobytes() + b"\x00\x00\x00\x00"]  # padded


class FakeTrack:
    def __init__(self, frames):
        self._frames = list(frames)

    async def recv(self):
        if not self._frames:
            raise EOFError("ended")
        return self._frames.pop(0)


class HangingTrack:
    async def recv(self):
        await asyncio.Event().wait()


async def test_pcm_from_frame_downmixes_stereo_and_strips_padding():
    f = FakeFrame([100, 300, 200, 400], channels=2)
    out, rate = pcm_from_frame(f)
    assert rate == 48000
    assert array.array("h", out).tolist() == [200, 300]


async def test_inbound_yields_pcm_frames():
    # 3 x 20 ms of 48 kHz constant 3000 -> 3 frames of 320 samples @16k
    frames = [FakeFrame([3000] * 960) for _ in range(3)]
    ia = InboundAudio(FakeTrack(frames))
    out = [f async for f in ia.frames()]
    assert len(out) == 3
    assert all(len(f) == FRAME16 for f in out)
    # steady-state samples preserved by resampling
    samples = array.array("h", out[1]).tolist()
    assert all(abs(s - 3000) <= 2 for s in samples)


async def test_inbound_reframes_odd_sized_frames():
    frames = [FakeFrame([1000] * 480) for _ in range(4)]  # 10 ms each @48k
    out = [f async for f in InboundAudio(FakeTrack(frames)).frames()]
    assert len(out) == 2 and all(len(f) == FRAME16 for f in out)


async def test_inbound_stop_ends_iterator_cleanly():
    ia = InboundAudio(HangingTrack())
    it = ia.frames()
    task = asyncio.ensure_future(it.__anext__())
    await settle()
    assert not task.done()
    ia.stop()
    with pytest.raises(StopAsyncIteration):
        await asyncio.wait_for(task, 1)
    await it.aclose()
    # frames() after stop is empty
    assert [f async for f in ia.frames()] == []


async def test_resampler_ratio_and_stateful_chunks():
    r = Pcm16Resampler(48000, 16000)
    data = array.array("h", range(0, 960 * 3, 1)).tobytes()
    whole = Pcm16Resampler(48000, 16000).process(data)
    parts = r.process(data[:1000]) + r.process(data[1000:])
    assert parts == whole
    assert len(whole) // 2 == 960  # 2880 in -> 960 out


@pytest.mark.integration
async def test_real_pyav_decode_roundtrip():
    av = pytest.importorskip("av")
    pytest.importorskip("aiortc")
    from app.realtime.media import decode_to_pcm48k

    import io
    import math

    buf = io.BytesIO()
    c = av.open(buf, "w", format="wav")
    s = c.add_stream("pcm_s16le", rate=16000, layout="mono")
    samples = array.array("h", [int(8000 * math.sin(i / 10)) for i in range(16000)])
    fr = av.AudioFrame.from_ndarray(
        __import__("numpy").array([samples], dtype="int16"), format="s16", layout="mono"
    )
    fr.sample_rate = 16000
    for p in s.encode(fr):
        c.mux(p)
    for p in s.encode(None):
        c.mux(p)
    c.close()
    out = decode_to_pcm48k(buf.getvalue())
    assert abs(len(out) // 2 - 48000) < 480
