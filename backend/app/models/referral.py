import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, uuid_pk


class Referral(Base):
    __tablename__ = "referrals"

    id: Mapped[uuid.UUID] = uuid_pk()
    category: Mapped[str] = mapped_column(String(64), index=True)  # GBV, crisis, clinic, pharmacy, helpline...
    name: Mapped[str] = mapped_column(String(255))
    contact: Mapped[str] = mapped_column(String(255))
    district: Mapped[str | None] = mapped_column(String(128))
    languages: Mapped[Any] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
