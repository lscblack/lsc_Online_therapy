import httpx


class OpenRouterTTS:
    def __init__(
        self, api_key: str, model: str = "openai/tts-1",
        base_url: str = "https://openrouter.ai/api/v1", default_voice: str = "alloy",
    ):
        if not api_key or not model:
            raise ValueError("OpenRouterTTS requires non-empty api_key and model")
        self._key, self._model, self._base = api_key, model, base_url.rstrip("/")
        self._voice = default_voice

    async def synthesize(self, text: str, language: str, voice: str | None) -> bytes:
        body = {
            "model": self._model,
            "input": text,
            "voice": voice or self._voice,
            "response_format": "mp3",
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self._base}/audio/speech",
                headers={"Authorization": f"Bearer {self._key}"},
                json=body,
            )
            resp.raise_for_status()
            return resp.content
