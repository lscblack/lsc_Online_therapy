import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, uuid_pk


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = uuid_pk()
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True)
    action: Mapped[str] = mapped_column(String(128), index=True)
    target: Mapped[str | None] = mapped_column(String(255))
    meta: Mapped[Any] = mapped_column(
        "metadata", JSONB, default=dict, server_default=text("'{}'::jsonb"))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
