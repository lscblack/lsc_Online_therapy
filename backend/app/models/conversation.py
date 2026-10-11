import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at_col, uuid_pk


class ConversationMode(enum.StrEnum):
    text = "text"
    voice = "voice"


class MessageRole(enum.StrEnum):
    user = "user"
    assistant = "assistant"
    system = "system"


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True)
    mode: Mapped[ConversationMode] = mapped_column(
        Enum(ConversationMode, name="conversation_mode"), default=ConversationMode.text,
        server_default=ConversationMode.text.value)
    language: Mapped[str | None] = mapped_column(String(16))
    created_at: Mapped[datetime] = created_at_col()
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = uuid_pk()
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    role: Mapped[MessageRole] = mapped_column(Enum(MessageRole, name="message_role"))
    content: Mapped[str] = mapped_column(Text)
    citations: Mapped[Any] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    safety_flags: Mapped[Any] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = created_at_col()
