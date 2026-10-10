import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, uuid_pk


class Facility(Base):
    """Schema only for now; populated by the offline/facilities sub-project."""

    __tablename__ = "facilities"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(255))
    type: Mapped[str] = mapped_column(String(64))
    lat: Mapped[float | None] = mapped_column(Float)
    lng: Mapped[float | None] = mapped_column(Float)
    district: Mapped[str | None] = mapped_column(String(128), index=True)
    services: Mapped[Any] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    hours: Mapped[str | None] = mapped_column(String(255))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
