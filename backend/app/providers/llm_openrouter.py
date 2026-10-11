import asyncio
import json
from collections.abc import AsyncIterator

import httpx

from app.providers.base import ProviderError

# Free-tier / shared models are frequently rate-limited (429) or briefly unavailable (502/503).
# Retry the request a few times with backoff before giving up, so a transient blip does not
# degrade an answerable question to a referral.
_RETRY_STATUSES = (429, 502, 503)


class OpenRouterLLM:
    def __init__(self, api_key: str, model: str, base_url: str = "https://openrouter.ai/api/v1",
                 max_tokens: int = 1024, retries: int = 3, backoff: float = 1.5):
        if not api_key or not model:
            raise ValueError("OpenRouterLLM requires non-empty api_key and model")
        self._key, self._model, self._base = api_key, model, base_url.rstrip("/")
        self._max_tokens = max_tokens
        self._retries = retries
        self._backoff = backoff

    async def stream_chat(self, messages: list[dict], **opts) -> AsyncIterator[str]:
        # Always cap max_tokens: OpenRouter rejects (402) a request whose worst-case output
        # (the model's full context when uncapped) exceeds the key's affordable balance,
        # even when the actual answer is tiny. Callers may override via opts.
        if self._max_tokens and "max_tokens" not in opts:
            opts = {"max_tokens": self._max_tokens, **opts}
        body = {"model": self._model, "messages": messages, **opts, "stream": True}
        headers = {"Authorization": f"Bearer {self._key}"}
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, read=120.0)) as client:
            for attempt in range(self._retries + 1):
                async with client.stream(
                    "POST", f"{self._base}/chat/completions", json=body, headers=headers
                ) as resp:
                    if resp.status_code in _RETRY_STATUSES and attempt < self._retries:
                        await resp.aread()
                        await asyncio.sleep(self._backoff * (2 ** attempt))
                        continue
                    if resp.status_code >= 400:
                        await resp.aread()
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line.startswith("data:"):  # skips blanks and ": comment" keepalives
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            return
                        try:
                            event = json.loads(data)
                        except json.JSONDecodeError as exc:
                            raise ProviderError(
                                f"Malformed SSE data from provider: {data[:200]!r}") from exc
                        if isinstance(event, dict) and event.get("error"):
                            raise ProviderError(f"Provider stream error: {event['error']}")
                        for choice in event.get("choices") or []:
                            content = (choice.get("delta") or {}).get("content")
                            if content:
                                yield content
                    return
