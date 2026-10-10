import builtins
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog


class AuditRepository:
    """Flush only; the calling service owns the commit."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record(self, actor_id: uuid.UUID | None, action: str, target: str | None = None,
                     metadata: dict[str, Any] | None = None) -> AuditLog:
        row = AuditLog(actor_id=actor_id, action=action, target=target, meta=metadata or {})
        self.session.add(row)
        await self.session.flush()
        return row

    async def list(self, limit: int = 100, offset: int = 0) -> builtins.list[AuditLog]:
        res = await self.session.execute(
            select(AuditLog).order_by(AuditLog.at.desc(), AuditLog.id)
            .limit(limit).offset(offset))
        return list(res.scalars())
