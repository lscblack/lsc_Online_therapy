from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable


class ProviderError(RuntimeError):
    """An external provider reported an error (e.g. mid-stream SSE error event)."""


@dataclass
class Transcript:
    text: str
    language: str | None = None


@runtime_checkable
class LLMProvider(Protocol):
    def stream_chat(self, messages: list[dict], **opts) -> AsyncIterator[str]: ...


@runtime_checkable
class EmbeddingProvider(Protocol):
    async def embed(
        self, texts: list[str], kind: Literal["query", "passage"]
    ) -> list[list[float]]: ...


@runtime_checkable
class STTProvider(Protocol):
    async def transcribe(self, audio: bytes, language: str | None) -> Transcript: ...


@runtime_checkable
class TTSProvider(Protocol):
    async def synthesize(self, text: str, language: str, voice: str | None) -> bytes: ...
