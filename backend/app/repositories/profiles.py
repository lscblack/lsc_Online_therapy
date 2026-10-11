import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation, Message
from app.models.profile import Profile


class ProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, user_id: uuid.UUID) -> Profile | None:
        return await self.session.get(Profile, user_id)

    # Repositories flush only; the calling service owns the commit.
    async def upsert(self, user_id: uuid.UUID, fields: dict) -> Profile:
        profile = await self.get(user_id)
        if profile is None:
            profile = Profile(user_id=user_id, **fields)
        else:
            for k, v in fields.items():
                setattr(profile, k, v)
        self.session.add(profile)
        await self.session.flush()
        await self.session.refresh(profile)
        return profile

    async def delete(self, user_id: uuid.UUID) -> None:
        await self.session.execute(delete(Profile).where(Profile.user_id == user_id))
        await self.session.flush()

    async def delete_history(self, user_id: uuid.UUID) -> None:
        """Delete all of the user's conversations and their messages."""
        conv_ids = select(Conversation.id).where(Conversation.user_id == user_id)
        await self.session.execute(delete(Message).where(Message.conversation_id.in_(conv_ids)))
        await self.session.execute(delete(Conversation).where(Conversation.user_id == user_id))
        await self.session.flush()
