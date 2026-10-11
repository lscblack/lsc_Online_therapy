import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, LargeBinary, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AgeBand(enum.StrEnum):
    under15 = "under15"
    age_15_17 = "15_17"
    age_18_19 = "18_19"
    age_20_24 = "20_24"
    age_25_plus = "25_plus"
    undisclosed = "undisclosed"


class Profile(Base):
    __tablename__ = "profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    nickname: Mapped[str | None] = mapped_column(String(64))
    age_band: Mapped[AgeBand] = mapped_column(
        Enum(AgeBand, name="age_band", values_callable=lambda e: [m.value for m in e]),
        default=AgeBand.undisclosed, server_default=AgeBand.undisclosed.value)
    gender: Mapped[str | None] = mapped_column(String(32))
    pronouns: Mapped[str | None] = mapped_column(String(32))
    tone_pref: Mapped[str | None] = mapped_column(String(32))
    interests: Mapped[Any] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    sensitive_context_enc: Mapped[bytes | None] = mapped_column(LargeBinary)
    consent: Mapped[Any] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
