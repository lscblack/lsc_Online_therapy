import uuid

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AppSetting


class SettingsRepository:
    """Read/write runtime key/value settings. Writes do not commit (the caller owns the txn)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, key: str) -> str | None:
        row = await self.session.get(AppSetting, key)
        return row.value if row else None

    async def set(self, key: str, value: str, updated_by: uuid.UUID | None = None) -> None:
        stmt = insert(AppSetting).values(key=key, value=value, updated_by=updated_by)
        stmt = stmt.on_conflict_do_update(
            index_elements=[AppSetting.key],
            set_={"value": value, "updated_by": updated_by, "updated_at": func.now()},
        )
        await self.session.execute(stmt)
