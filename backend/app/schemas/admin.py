import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.user import UserRole
from app.schemas.document import DocumentOut, ReviewIn

__all__ = ["AdminLoginRequest", "AuditOut", "DocumentOut", "ModelInfo", "ModelConfigOut",
           "SetModelIn", "TestModelIn", "TestModelOut", "ReviewIn", "UserOut"]


class AdminLoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=256)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str | None
    role: UserRole
    is_upgraded: bool
    locale: str
    disabled: bool
    created_at: datetime
    last_seen_at: datetime | None


class AuditOut(BaseModel):
    id: uuid.UUID
    actor_id: uuid.UUID | None
    action: str
    target: str | None
    metadata: Any
    at: datetime

    @classmethod
    def from_row(cls, r) -> "AuditOut":
        return cls(id=r.id, actor_id=r.actor_id, action=r.action, target=r.target,
                   metadata=r.meta, at=r.at)


class AdminMeOut(BaseModel):
    role: UserRole
    email: str | None


class ModelInfo(BaseModel):
    id: str
    label: str
    tier: str
    note: str


class ModelConfigOut(BaseModel):
    active: str          # the model currently used for chat/voice
    default: str         # the env default (used when no override is set)
    is_override: bool    # True when `active` comes from the DB override, not the env default
    provider: str        # the LLM provider (e.g. "openrouter")
    catalog: list[ModelInfo]


class SetModelIn(BaseModel):
    model: str = Field(min_length=1, max_length=255)


class TestModelIn(BaseModel):
    model: str = Field(min_length=1, max_length=255)
    prompt: str = Field(default="What contraception methods are available?",
                        min_length=1, max_length=500)


class TestModelOut(BaseModel):
    model: str
    ok: bool
    latency_ms: int
    sample: str = ""
    error: str | None = None
