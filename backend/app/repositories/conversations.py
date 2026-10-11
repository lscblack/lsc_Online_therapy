import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.models.conversation import Conversation, ConversationMode, Message, MessageRole


class ConversationRepository:
    """Repositories flush only; the calling service owns the commit."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_conversation(self, user: User, mode: str = "text",
                                  language: str | None = None) -> Conversation:
        conv = Conversation(user_id=user.id, mode=ConversationMode(mode), language=language)
        self.session.add(conv)
        await self.session.flush()
        return conv

    async def get_conversation(self, conversation_id: uuid.UUID, user: User) -> Conversation | None:
        """Ownership-scoped: another user's conversation is indistinguishable from a missing one."""
        stmt = select(Conversation).where(Conversation.id == conversation_id,
                                          Conversation.user_id == user.id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def add_message(self, conversation_id: uuid.UUID, role: str, content: str,
                          citations: list | None = None,
                          safety_flags: dict | None = None) -> Message:
        msg = Message(conversation_id=conversation_id, role=MessageRole(role), content=content,
                      citations=citations or [], safety_flags=safety_flags or {})
        self.session.add(msg)
        conv = await self.session.get(Conversation, conversation_id)
        if conv is not None:
            conv.last_message_at = datetime.now(UTC)
        await self.session.flush()
        return msg

    async def get_history(self, conversation_id: uuid.UUID, limit: int = 10) -> list[dict]:
        """Most recent `limit` user/assistant turns, oldest first, as {"role","content"}."""
        stmt = (select(Message).where(Message.conversation_id == conversation_id,
                                      Message.role.in_([MessageRole.user, MessageRole.assistant]))
                .order_by(Message.created_at.desc(), Message.id.desc()).limit(limit))
        rows = list((await self.session.execute(stmt)).scalars())
        return [{"role": m.role.value, "content": m.content} for m in reversed(rows)]
