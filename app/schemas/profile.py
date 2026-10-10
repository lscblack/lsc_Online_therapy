from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.profile import AgeBand

SENSITIVE_MAX = 2000


class ProfileUpdate(BaseModel):
    """PUT body. Only supplied fields change (omitted = untouched)."""
    model_config = ConfigDict(extra="forbid")

    nickname: str | None = Field(default=None, max_length=64)
    age_band: AgeBand | None = None
    gender: str | None = Field(default=None, max_length=32)
    pronouns: str | None = Field(default=None, max_length=32)
    tone_pref: str | None = Field(default=None, max_length=32)
    interests: list[str] | None = Field(default=None, max_length=50)
    # OPTIONAL plaintext health context (sent over TLS, stored AES-GCM encrypted).
    # Omit = unchanged; null = clear it and revoke consent.
    sensitive_context: str | None = Field(default=None, max_length=SENSITIVE_MAX)


class ProfileOut(BaseModel):
    nickname: str | None
    age_band: AgeBand
    gender: str | None
    pronouns: str | None
    tone_pref: str | None
    interests: list[str]
    sensitive_context: str | None = None  # decrypted; optional
    consent: dict[str, Any]
    updated_at: datetime | None
