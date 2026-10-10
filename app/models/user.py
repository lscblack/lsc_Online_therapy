import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at_col, uuid_pk


class UserRole(enum.StrEnum):
    user = "user"
    reviewer = "reviewer"
    admin = "admin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = uuid_pk()
    anon_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(320), unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"), default=UserRole.user,
        server_default=UserRole.user.value)
    is_upgraded: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    recovery_hash: Mapped[str | None] = mapped_column(String(255))
    locale: Mapped[str] = mapped_column(String(16), default="rw", server_default="rw")
    disabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    created_at: Mapped[datetime] = created_at_col()
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
