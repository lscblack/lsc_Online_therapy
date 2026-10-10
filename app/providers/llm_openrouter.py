import json
from collections.abc import AsyncIterator

import httpx


class OpenRouterLLM:
    def __init__(self, api_key: str, model: str, base_url: str = "https://openrouter.ai/api/v1"):
        self._key, self._model, self._base = api_key, model, base_url.rstrip("/")

    async def stream_chat(self, messages: list[dict], **opts) -> AsyncIterator[str]:
        body = {"model": self._model, "messages": messages, **opts, "stream": True}
        headers = {"Authorization": f"Bearer {self._key}"}
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, read=120.0)) as client:
            async with client.stream(
                "POST", f"{self._base}/chat/completions", json=body, headers=headers
            ) as resp:
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
                    except json.JSONDecodeError:
                        continue
                    for choice in event.get("choices") or []:
                        content = (choice.get("delta") or {}).get("content")
                        if content:
                            yield content
