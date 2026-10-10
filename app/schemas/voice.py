import uuid
from typing import Any

from pydantic import BaseModel, Field, field_validator


class TranscribeResponse(BaseModel):
    text: str
    language: str | None = None


class SpeakRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    language: str = Field(default="en", max_length=16)
    voice: str | None = Field(default=None, max_length=64)

    @field_validator("text")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("text must not be blank")
        return v.strip()


class VoiceChatResponse(BaseModel):
    """Voice turn. The reply audio is returned inline as base64 (`audio_base64`, MIME in
    `audio_mime`) so one round trip carries transcript, guarded answer, safety metadata and audio."""
    transcript: str
    answer: str
    citations: list[dict[str, Any]]
    conversation_id: uuid.UUID
    safety_flags: dict[str, Any]
    language: str
    audio_base64: str  # empty when tts_available is False
    audio_mime: str
    tts_available: bool = True
