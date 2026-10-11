import httpx

from app.providers.base import Transcript

_AUDIO_MIME = {
    "webm": "audio/webm", "ogg": "audio/ogg", "opus": "audio/ogg", "wav": "audio/wav",
    "mp3": "audio/mpeg", "m4a": "audio/mp4", "mp4": "audio/mp4", "flac": "audio/flac",
}


class OpenRouterWhisperSTT:
    def __init__(
        self, api_key: str, model: str = "openai/whisper-1",
        base_url: str = "https://openrouter.ai/api/v1",
    ):
        if not api_key or not model:
            raise ValueError("OpenRouterWhisperSTT requires non-empty api_key and model")
        self._key, self._model, self._base = api_key, model, base_url.rstrip("/")

    async def transcribe(
        self, audio: bytes, language: str | None, filename: str | None = None
    ) -> Transcript:
        """filename's extension tells Whisper-style endpoints the audio format."""
        filename = filename or "audio.webm"
        mime = _AUDIO_MIME.get(filename.rsplit(".", 1)[-1].lower(), "application/octet-stream")
        data = {"model": self._model}
        if language:
            data["language"] = language
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self._base}/audio/transcriptions",
                headers={"Authorization": f"Bearer {self._key}"},
                data=data,
                files={"file": (filename, audio, mime)},
            )
            resp.raise_for_status()
            payload = resp.json()
        return Transcript(text=payload.get("text", ""), language=payload.get("language") or language)
