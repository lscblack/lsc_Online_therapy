import asyncio
import json
from collections.abc import AsyncIterator

import httpx

from app.providers.base import ProviderError

# Transient statuses worth retrying (free/shared providers rate-limit aggressively).
_RETRY_STATUSES = (429, 502, 503)


class OpenAICompatLLM:
    """A chat LLM for any OpenAI-compatible endpoint (OpenRouter, Requesty, Ollama, NVIDIA,
    Cohere compat, AionLabs, HuggingFace router, ...).

    Yields only assistant *content* — reasoning tokens (`delta.reasoning` /
    `reasoning_content`, emitted by "thinking" models) are ignored so the answer is never the
    model's scratchpad, and are not what starves the output: we also send a generous max_tokens.
    """

    def __init__(self, base_url: str, api_key: str | None, model: str, *,
                 max_tokens: int = 1024, extra_headers: dict | None = None,
                 retries: int = 3, backoff: float = 1.2, timeout: float = 120.0):
        if not base_url or not model:
            raise ValueError("OpenAICompatLLM requires base_url and model")
        self._base = base_url.rstrip("/")
        self._key = api_key
        self._model = model
        self._max_tokens = max_tokens
        self._extra = extra_headers or {}
        self._retries = retries
        self._backoff = backoff
        self._timeout = timeout

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json", **self._extra}
        if self._key:
            h["Authorization"] = f"Bearer {self._key}"
        return h

    async def stream_chat(self, messages: list[dict], **opts) -> AsyncIterator[str]:
        if self._max_tokens and "max_tokens" not in opts:
            opts = {"max_tokens": self._max_tokens, **opts}
        body = {"model": self._model, "messages": messages, **opts, "stream": True}
        url = f"{self._base}/chat/completions"
        async with httpx.AsyncClient(timeout=httpx.Timeout(self._timeout, read=self._timeout)) as client:
            for attempt in range(self._retries + 1):
                async with client.stream("POST", url, json=body, headers=self._headers()) as resp:
                    if resp.status_code in _RETRY_STATUSES and attempt < self._retries:
                        await resp.aread()
                        await asyncio.sleep(self._backoff * (2 ** attempt))
                        continue
                    if resp.status_code >= 400:
                        await resp.aread()
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            return
                        try:
                            event = json.loads(data)
                        except json.JSONDecodeError as exc:
                            raise ProviderError(f"Malformed SSE data: {data[:200]!r}") from exc
                        if isinstance(event, dict) and event.get("error"):
                            raise ProviderError(f"Provider stream error: {event['error']}")
                        for choice in event.get("choices") or []:
                            delta = choice.get("delta") or {}
                            content = delta.get("content")
                            if content:
                                yield content
                    return
