import uuid
from typing import Any

from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: uuid.UUID | None = None
    language: str | None = Field(default=None, max_length=16)

    @field_validator("message")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("message must not be blank")
        return v.strip()


class ChatResponse(BaseModel):
    answer: str
    citations: list[dict[str, Any]]
    conversation_id: uuid.UUID
    safety_flags: dict[str, Any]
    language: str
