import hashlib
import random
from collections.abc import AsyncIterator
from typing import Literal

from app.providers.base import Transcript

DIM = 768


class FakeLLM:
    def __init__(self, chunks: list[str] | None = None):
        self.chunks = chunks if chunks is not None else ["Hello", " from", " fake."]
        self.calls: list[dict] = []

    async def stream_chat(self, messages: list[dict], **opts) -> AsyncIterator[str]:
        self.calls.append({"messages": messages, "opts": opts})
        for c in self.chunks:
            yield c


class FakeEmbeddings:
    """Deterministic hash-seeded unit vectors; no torch."""

    async def embed(
        self, texts: list[str], kind: Literal["query", "passage"]
    ) -> list[list[float]]:
        out = []
        for t in texts:
            seed = int.from_bytes(hashlib.sha256(f"{kind}:{t}".encode()).digest()[:8], "big")
            rng = random.Random(seed)
            v = [rng.uniform(-1, 1) for _ in range(DIM)]
            n = sum(x * x for x in v) ** 0.5
            out.append([x / n for x in v])
        return out


class FakeSTT:
    def __init__(self, text: str = "fake transcript", language: str | None = "en"):
        self.text, self.language = text, language

    async def transcribe(self, audio: bytes, language: str | None) -> Transcript:
        return Transcript(text=self.text, language=language or self.language)


class FakeTTS:
    async def synthesize(self, text: str, language: str, voice: str | None) -> bytes:
        return b"FAKE-MP3:" + text.encode()
