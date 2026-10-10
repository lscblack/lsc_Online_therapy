from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.referral import Referral


class ReferralRepository:
    """Repositories flush only; the calling service owns the commit."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def lookup(self, category: str, district: str | None = None,
                     limit: int = 10) -> list[Referral]:
        """Referrals of a category; district matches first, then national (district NULL),
        and other districts only when no district is requested. Verified entries first."""
        stmt = select(Referral).where(Referral.category == category)
        if district:
            stmt = stmt.where((Referral.district == district) | (Referral.district.is_(None)))
            local_first = case((Referral.district == district, 0), else_=1)
        else:
            local_first = case((Referral.district.is_(None), 0), else_=1)
        verified_first = case((Referral.verified_at.is_not(None), 0), else_=1)
        stmt = stmt.order_by(local_first, verified_first, Referral.name, Referral.id).limit(limit)
        return list((await self.session.execute(stmt)).scalars())

    async def upsert(self, *, category: str, name: str, contact: str,
                     district: str | None = None, languages: list[str] | None = None,
                     verified_at=None) -> Referral:
        """Idempotent on (category, name, district)."""
        stmt = select(Referral).where(Referral.category == category, Referral.name == name)
        stmt = stmt.where(Referral.district.is_(None) if district is None
                          else Referral.district == district)
        row = (await self.session.execute(stmt.limit(1))).scalar_one_or_none()
        if row is None:
            row = Referral(category=category, name=name, contact=contact, district=district,
                           languages=languages or [], verified_at=verified_at)
            self.session.add(row)
        else:
            row.contact, row.languages, row.verified_at = contact, languages or [], verified_at
        await self.session.flush()
        return row
