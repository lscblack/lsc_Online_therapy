import httpx

from app.providers.base import Transcript


class OpenRouterWhisperSTT:
    def __init__(
        self, api_key: str, model: str = "openai/whisper-1",
        base_url: str = "https://openrouter.ai/api/v1",
    ):
        self._key, self._model, self._base = api_key, model, base_url.rstrip("/")

    async def transcribe(self, audio: bytes, language: str | None) -> Transcript:
        data = {"model": self._model}
        if language:
            data["language"] = language
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self._base}/audio/transcriptions",
                headers={"Authorization": f"Bearer {self._key}"},
                data=data,
                files={"file": ("audio.webm", audio, "application/octet-stream")},
            )
            resp.raise_for_status()
            payload = resp.json()
        return Transcript(text=payload.get("text", ""), language=payload.get("language") or language)
