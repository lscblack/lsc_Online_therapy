"""aiortc media tracks: inbound audio sink and cancellable outbound TTS source.

Inbound: `InboundAudio` pulls frames from an aiortc audio track and yields PCM16 mono
16 kHz 20 ms frames (the format the VAD/STT path expects).

Outbound: `TtsTrack` is a pull-based source track. aiortc calls `recv()` once per 20 ms;
we hand back the next 20 ms of queued TTS audio (PCM16 mono 48 kHz) or silence. `cancel()`
flushes everything instantly (barge-in).

aiortc / pyav (`av`) are imported lazily, so this module imports and all framing /
queueing / cancel logic is unit-testable with fakes. The real decode path lives behind
`decode_to_pcm48k` and the default frame factory.
"""
import array
import asyncio
import io
import time
from collections import deque
from collections.abc import AsyncIterator, Callable
from typing import Any

IN_RATE = 16000
OUT_RATE = 48000
FRAME_MS = 20


def _frame_bytes(rate: int) -> int:
    return rate * FRAME_MS // 1000 * 2


# ---------------------------------------------------------------- PCM helpers


class Pcm16Resampler:
    """Streaming mono PCM16 resampler (stateful across chunks).

    Integer decimation (e.g. 48k->16k) uses block averaging (cheap anti-alias);
    other ratios use linear interpolation.
    """

    def __init__(self, src_rate: int, dst_rate: int):
        self.src, self.dst = src_rate, dst_rate
        self._buf: list[int] = []
        self._pos = 0  # input position * dst (relative to _buf[0])
        self._tail = b""  # odd trailing byte

    def process(self, data: bytes) -> bytes:
        data = self._tail + data
        n = len(data) // 2
        self._tail = data[n * 2 :]
        samples = array.array("h")
        samples.frombytes(data[: n * 2])
        if self.src == self.dst:
            return samples.tobytes()
        self._buf.extend(samples)
        out = array.array("h")
        buf = self._buf
        if self.src % self.dst == 0:
            w = self.src // self.dst
            blocks = len(buf) // w
            for b in range(blocks):
                out.append(sum(buf[b * w : (b + 1) * w]) // w)
            del buf[: blocks * w]
        else:
            pos = self._pos
            while pos // self.dst + 1 < len(buf):
                i, frac = divmod(pos, self.dst)
                out.append((buf[i] * (self.dst - frac) + buf[i + 1] * frac) // self.dst)
                pos += self.src
            used = pos // self.dst
            del buf[:used]
            self._pos = pos - used * self.dst
        return out.tobytes()


def pcm_from_frame(frame: Any) -> tuple[bytes, int]:
    """aiortc/pyav audio frame (s16, packed) -> (mono PCM16 bytes, sample_rate)."""
    channels = len(frame.layout.channels) if _is_seq(frame.layout.channels) else frame.layout.channels
    raw = bytes(frame.planes[0])[: frame.samples * channels * 2]
    if channels > 1:
        s = array.array("h")
        s.frombytes(raw)
        mono = array.array("h", (sum(s[i : i + channels]) // channels for i in range(0, len(s), channels)))
        raw = mono.tobytes()
    return raw, frame.sample_rate


def _is_seq(x: Any) -> bool:
    return hasattr(x, "__len__")


class _Reframer:
    def __init__(self, size: int):
        self.size = size
        self._buf = bytearray()

    def push(self, data: bytes) -> list[bytes]:
        self._buf += data
        out = []
        while len(self._buf) >= self.size:
            out.append(bytes(self._buf[: self.size]))
            del self._buf[: self.size]
        return out


# -------------------------------------------------------------------- inbound


class InboundAudio:
    """Consumes an aiortc audio track; `frames()` yields PCM16/16k/mono/20 ms frames."""

    def __init__(self, track: Any, *, rate: int = IN_RATE):
        self._track = track
        self._rate = rate
        self._stopped = asyncio.Event()

    def stop(self) -> None:
        self._stopped.set()

    async def frames(self) -> AsyncIterator[bytes]:
        reframer = _Reframer(_frame_bytes(self._rate))
        resamplers: dict[int, Pcm16Resampler] = {}
        stop_wait = asyncio.ensure_future(self._stopped.wait())
        recv: asyncio.Future | None = None
        try:
            while not self._stopped.is_set():
                recv = asyncio.ensure_future(self._track.recv())
                await asyncio.wait({recv, stop_wait}, return_when=asyncio.FIRST_COMPLETED)
                if not recv.done():  # stopped while waiting
                    return
                try:
                    frame = recv.result()
                except Exception:  # track ended (MediaStreamError) or failed
                    return
                finally:
                    recv = None
                raw, rate = pcm_from_frame(frame)
                rs = resamplers.get(rate) or resamplers.setdefault(rate, Pcm16Resampler(rate, self._rate))
                for f in reframer.push(rs.process(raw)):
                    yield f
        finally:
            for fut in (recv, stop_wait):
                if fut is not None and not fut.done():
                    fut.cancel()
            await asyncio.gather(*(f for f in (recv, stop_wait) if f is not None), return_exceptions=True)


# ------------------------------------------------------------------- outbound


def decode_to_pcm48k(data: bytes) -> bytes:
    """Decode any container/codec pyav understands (mp3, wav, ...) to PCM16 mono 48 kHz."""
    import av  # lazy

    out = bytearray()
    with av.open(io.BytesIO(data)) as container:
        resampler = av.AudioResampler(format="s16", layout="mono", rate=OUT_RATE)
        for frame in container.decode(audio=0):
            for rf in resampler.resample(frame):
                out += bytes(rf.planes[0])[: rf.samples * 2]
        for rf in resampler.resample(None) or []:
            out += bytes(rf.planes[0])[: rf.samples * 2]
    return bytes(out)


def _av_frame(pcm: bytes, pts: int, rate: int) -> Any:
    import av  # lazy

    frame = av.AudioFrame(format="s16", layout="mono", samples=len(pcm) // 2)
    frame.planes[0].update(pcm)
    frame.sample_rate = rate
    frame.pts = pts
    frame.time_base = __import__("fractions").Fraction(1, rate)
    return frame


def _base_track_cls() -> type:
    try:
        from aiortc import MediaStreamTrack

        return MediaStreamTrack
    except Exception:  # aiortc missing/unusable: app must still boot
        class _Stub:
            kind = "audio"

            def __init__(self) -> None:
                pass

            def stop(self) -> None:
                pass

        return _Stub


class TtsTrack(_base_track_cls()):  # type: ignore[misc]
    """Outbound audio source with instant cancel.

    play(chunks)  enqueue an utterance (bytes or async iterator of bytes). Utterances
                  play back-to-back in call order.
    cancel()      synchronously flush all queued/in-flight audio and stop the feeder
                  task; next recv() is silence. Safe to call anytime; track stays usable.
    is_playing    True while audio is queued, being fed, or buffered.
    recv()        always returns exactly one 20 ms mono s16 48 kHz frame (silence when idle),
                  with pts advancing 960/frame, time_base 1/48000. Never raises on cancel.

    input_format: "encoded" (default; decoded with `decoder`, default pyav -> mp3/wav...)
    or "pcm16" (chunks are raw PCM16 mono at `input_rate`, streamed/resampled as they arrive).
    Encoded iterators are buffered whole before decoding (mp3 can't be decoded mid-frame).
    """

    kind = "audio"

    def __init__(
        self,
        *,
        input_format: str = "encoded",
        input_rate: int = OUT_RATE,
        decoder: Callable[[bytes], bytes] | None = None,
        frame_factory: Callable[[bytes, int, int], Any] | None = None,
        pace: bool = True,
    ):
        super().__init__()
        self._encoded = input_format != "pcm16"
        self._input_rate = input_rate
        self._decoder = decoder or decode_to_pcm48k
        self._factory = frame_factory or _av_frame
        self._pace = pace
        self._frame_size = _frame_bytes(OUT_RATE)
        self._buf = bytearray()
        self._pending: deque = deque()
        self._feeder: asyncio.Task | None = None
        self._pts = 0
        self._t0: float | None = None

    @property
    def is_playing(self) -> bool:
        return bool(self._pending) or bool(self._buf) or (self._feeder is not None and not self._feeder.done())

    # -- control
    def play(self, chunks: "AsyncIterator[bytes] | bytes") -> None:
        self._pending.append(chunks)
        if self._feeder is None or self._feeder.done():
            self._feeder = asyncio.ensure_future(self._feed())

    def cancel(self) -> None:
        self._pending.clear()
        self._buf.clear()
        feeder, self._feeder = self._feeder, None
        if feeder is not None and not feeder.done():
            feeder.cancel()

    def stop(self) -> None:
        self.cancel()
        super().stop()

    # -- feeding
    async def _feed(self) -> None:
        while self._pending:
            src = self._pending.popleft()
            if self._encoded:
                data = src if isinstance(src, bytes) else b"".join([c async for c in src])
                pcm = await asyncio.get_running_loop().run_in_executor(None, self._decoder, data)
                self._buf += pcm
            else:
                rs = Pcm16Resampler(self._input_rate, OUT_RATE)
                if isinstance(src, bytes):
                    self._buf += rs.process(src)
                else:
                    async for c in src:
                        self._buf += rs.process(c)

    # -- aiortc pull
    async def recv(self) -> Any:
        if self._pace:
            now = time.monotonic()
            if self._t0 is None:
                self._t0 = now
            delay = self._t0 + self._pts / OUT_RATE - now
            await asyncio.sleep(max(delay, 0))
        n = self._frame_size
        chunk = bytes(self._buf[:n])
        del self._buf[:n]
        if len(chunk) < n:
            chunk += bytes(n - len(chunk))
        frame = self._factory(chunk, self._pts, OUT_RATE)
        self._pts += n // 2
        return frame
