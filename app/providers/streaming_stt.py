"""Streaming STT: interface, VAD-segmented batch adapter, word-level vendor, and a fake."""
import io
import json
import wave
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from app.providers.base import ProviderError, STTProvider


@dataclass
class STTEvent:
    text: str
    is_final: bool
    language: str | None = None


@runtime_checkable
class StreamingSTTProvider(Protocol):
    def stream(
        self, frames: AsyncIterator[bytes], language: str | None
    ) -> AsyncIterator[STTEvent]: ...


def pcm_to_wav(pcm: bytes, sample_rate: int = 16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm)
    return buf.getvalue()


class VadSegmentedSTT:
    """Cut utterances with VAD, transcribe each via batch STT; one final event per utterance.

    `vad` is a callable frames -> AsyncIterator[VadEvent] (default: app.realtime.vad.segment).
    """

    def __init__(self, batch_stt: STTProvider, vad: Callable | None = None,
                 sample_rate: int = 16000):
        if vad is None:
            from app.realtime.vad import segment as vad
        self._stt, self._vad, self._rate = batch_stt, vad, sample_rate

    async def stream(self, frames: AsyncIterator[bytes], language: str | None
                     ) -> AsyncIterator[STTEvent]:
        async for ev in self._vad(frames):
            if ev.type != "speech_end" or not ev.audio:
                continue
            t = await self._stt.transcribe(pcm_to_wav(ev.audio, self._rate), language,
                                           filename="utterance.wav")
            text = (t.text or "").strip()
            if text:
                yield STTEvent(text=text, is_final=True, language=t.language or language)


class StreamingVendorSTT:
    """Deepgram-style websocket streaming (English fast path). Network only; not unit-tested."""

    def __init__(self, api_key: str, model: str, url: str, sample_rate: int = 16000):
        if not api_key:
            from app.providers.factory import ProviderConfigError
            raise ProviderConfigError("STREAMING_STT_API_KEY must be set to use this provider")
        self._key, self._model, self._url, self._rate = api_key, model, url, sample_rate

    async def stream(self, frames: AsyncIterator[bytes], language: str | None
                     ) -> AsyncIterator[STTEvent]:
        import asyncio

        import websockets  # lazy

        qs = (f"model={self._model}&encoding=linear16&sample_rate={self._rate}&channels=1"
              f"&interim_results=true&endpointing=300&language={language or 'en'}")
        async with websockets.connect(
            f"{self._url}?{qs}", additional_headers={"Authorization": f"Token {self._key}"}
        ) as ws:
            async def pump():
                try:
                    async for f in frames:
                        await ws.send(f)
                finally:
                    await ws.send(json.dumps({"type": "CloseStream"}))

            task = asyncio.create_task(pump())
            try:
                async for raw in ws:
                    msg = json.loads(raw)
                    if msg.get("type") == "Error":
                        raise ProviderError(str(msg.get("description", "stt error")))
                    alts = (msg.get("channel") or {}).get("alternatives") or []
                    text = (alts[0].get("transcript") if alts else "") or ""
                    if text.strip():
                        yield STTEvent(text.strip(), bool(msg.get("is_final")), language)
            finally:
                task.cancel()


class FakeStreamingSTT:
    """Deterministic: yields the scripted events once the input stream is drained."""

    def __init__(self, events: list[STTEvent] | None = None):
        self.events = events if events is not None else [STTEvent("fake transcript", True, "en")]

    async def stream(self, frames: AsyncIterator[bytes], language: str | None
                     ) -> AsyncIterator[STTEvent]:
        async for _ in frames:
            pass
        for e in self.events:
            yield e
