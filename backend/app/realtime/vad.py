"""Server-side voice activity detection and utterance endpointing.

Input is PCM16 mono little-endian frames (default 16 kHz, 20 ms). A pluggable backend
decides speech/non-speech per frame; `VadSegmenter` turns that into speech_start /
speech_end events (speech_end carries the utterance audio). Heavy models are loaded
lazily behind a lock so the app and unit tests never import torch/webrtcvad.
"""
import array
import asyncio
import math
import threading
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal, Protocol

from app.core.config import Settings, get_settings


@dataclass
class VadEvent:
    type: Literal["speech_start", "speech_end"]
    audio: bytes = b""  # speech_end: the whole utterance (PCM16), incl. trailing silence


class VadBackend(Protocol):
    def is_speech(self, frame: bytes) -> bool: ...


class EnergyBackend:
    """RMS threshold. Dependency-free fallback and test backend."""

    def __init__(self, threshold: int = 500):
        self.threshold = threshold

    def is_speech(self, frame: bytes) -> bool:
        n = len(frame) // 2
        if n == 0:
            return False
        samples = array.array("h", frame[: n * 2])
        rms = math.sqrt(sum(x * x for x in samples) / n)
        return rms >= self.threshold


class WebRtcBackend:
    def __init__(self, sample_rate: int, aggressiveness: int):
        self._rate, self._aggr = sample_rate, aggressiveness
        self._vad = None
        self._lock = threading.Lock()

    def is_speech(self, frame: bytes) -> bool:
        if self._vad is None:
            with self._lock:
                if self._vad is None:
                    import webrtcvad  # lazy

                    self._vad = webrtcvad.Vad(self._aggr)
        return self._vad.is_speech(frame, self._rate)


_silero_model = None  # module-level: loaded once, used as a read-only template
_silero_lock = threading.Lock()


def _load_silero_template():
    global _silero_model
    if _silero_model is None:
        with _silero_lock:
            if _silero_model is None:
                from silero_vad import load_silero_vad  # lazy: imports torch

                _silero_model = load_silero_vad()
    return _silero_model


class SileroBackend:
    """silero-vad. One instance per stream: it owns a private copy of the (stateful) model
    and its PCM window buffer. Weights are loaded once per process. Inference is blocking,
    so segment() runs it via asyncio.to_thread (`blocking = True`)."""

    WINDOW = 512
    blocking = True

    def __init__(self, sample_rate: int, threshold: float):
        self._rate, self._thr = sample_rate, threshold
        self._model = None
        self._buf = b""
        self._last = False

    def load(self) -> None:
        if self._model is None:
            import copy

            self._model = copy.deepcopy(_load_silero_template())  # per-stream recurrent state
            if hasattr(self._model, "reset_states"):
                self._model.reset_states()

    def is_speech(self, frame: bytes) -> bool:
        self.load()
        import numpy as np
        import torch

        self._buf += frame
        step = self.WINDOW * 2
        while len(self._buf) >= step:
            chunk, self._buf = self._buf[:step], self._buf[step:]
            x = torch.from_numpy(np.frombuffer(chunk, dtype=np.int16).astype(np.float32) / 32768.0)
            self._last = float(self._model(x, self._rate).item()) >= self._thr
        return self._last


def make_backend(settings: Settings | None = None) -> VadBackend:
    """auto: silero -> webrtcvad -> energy, by availability (imports probed lazily)."""
    s = settings or get_settings()
    name = s.vad_backend
    order = ["silero", "webrtc", "energy"] if name == "auto" else [name]
    for n in order:
        if n == "energy":
            return EnergyBackend(s.vad_energy_threshold)
        mod = {"silero": "silero_vad", "webrtc": "webrtcvad"}.get(n)
        if mod is None:
            raise ValueError(f"Unknown VAD backend: {n!r}")
        try:
            __import__(mod)
        except ImportError:
            if name != "auto":
                raise
            continue
        if n == "silero":
            return SileroBackend(s.vad_sample_rate, s.vad_silero_threshold)
        return WebRtcBackend(s.vad_sample_rate, s.vad_aggressiveness)
    return EnergyBackend(s.vad_energy_threshold)


class VadSegmenter:
    """Stateful endpointer. feed(frame) -> list of VadEvent."""

    def __init__(self, backend: VadBackend, frame_ms: int, silence_ms: int, min_speech_ms: int):
        self._b = backend
        self._frame_ms, self._silence_ms, self._min_ms = frame_ms, silence_ms, min_speech_ms
        self._active = False
        self._buf: list[bytes] = []
        self._speech_ms = 0
        self._silence = 0
        self._pending: list[bytes] = []  # speech candidate not yet confirmed >= min_speech
        self._gap = 0  # consecutive non-speech frames inside a pending candidate

    def feed(self, frame: bytes) -> list[VadEvent]:
        out: list[VadEvent] = []
        speech = self._b.is_speech(frame)
        if not self._active:
            if speech:
                self._gap = 0
                self._pending.append(frame)
                self._speech_ms += self._frame_ms
                if self._speech_ms >= self._min_ms:
                    self._active = True
                    self._buf = self._pending
                    self._pending = []
                    self._silence = 0
                    out.append(VadEvent("speech_start"))
            elif self._pending and self._gap < 1:
                self._gap += 1  # tolerate a single flicker frame; keep audio contiguous
                self._pending.append(frame)
            else:
                self._pending, self._speech_ms, self._gap = [], 0, 0
            return out
        self._buf.append(frame)
        if speech:
            self._silence = 0
        else:
            self._silence += self._frame_ms
            if self._silence >= self._silence_ms:
                out.append(self._end())
        return out

    def flush(self) -> list[VadEvent]:
        """End of stream: close an open utterance."""
        return [self._end()] if self._active else []

    def _end(self) -> VadEvent:
        ev = VadEvent("speech_end", audio=b"".join(self._buf))
        self._active, self._buf, self._pending = False, [], []
        self._speech_ms = self._silence = self._gap = 0
        return ev


def is_speech(frame: bytes, backend: VadBackend | None = None) -> bool:
    """One-off verdict. With no backend a fresh one is made (never shared across callers)."""
    return (backend or make_backend()).is_speech(frame)


async def segment(
    frames: AsyncIterator[bytes],
    backend: VadBackend | None = None,
    *,
    frame_ms: int | None = None,
    silence_ms: int | None = None,
    min_speech_ms: int | None = None,
    settings: Settings | None = None,
) -> AsyncIterator[VadEvent]:
    """Endpoint a PCM frame stream. Each call gets its own backend/state unless one is
    injected (tests). Blocking backends (Silero) run in a worker thread. Closing this
    generator early also closes `frames`."""
    s = settings or get_settings()
    be = backend or make_backend(s)
    blocking = bool(getattr(be, "blocking", False))
    seg = VadSegmenter(
        be,
        frame_ms or s.vad_frame_ms,
        silence_ms if silence_ms is not None else s.vad_silence_ms,
        min_speech_ms if min_speech_ms is not None else s.vad_min_speech_ms,
    )
    try:
        if blocking and hasattr(be, "load"):
            await asyncio.to_thread(be.load)
        async for f in frames:
            events = await asyncio.to_thread(seg.feed, f) if blocking else seg.feed(f)
            for ev in events:
                yield ev
        for ev in seg.flush():
            yield ev
    finally:
        aclose = getattr(frames, "aclose", None)
        if aclose:
            await aclose()


detect = segment  # alias used by the task brief
