"""Referral catalog access + idempotent seed loader."""
import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.referral import Referral
from app.repositories.referrals import ReferralRepository

SEED_PATH = Path(__file__).parent / "data" / "referrals_seed.json"


async def lookup(session: AsyncSession, category: str, district: str | None = None) -> list[Referral]:
    return await ReferralRepository(session).lookup(category, district)


async def seed_referrals(session: AsyncSession, path: Path = SEED_PATH, commit: bool = True) -> int:
    """Upsert the seed file; safe to re-run. Seed entries are PLACEHOLDERS: `verified_at`
    is only set if the entry says verified=true (none do until HDI verifies them)."""
    entries = json.loads(Path(path).read_text(encoding="utf-8"))["referrals"]
    repo = ReferralRepository(session)
    for e in entries:
        await repo.upsert(
            category=e["category"], name=e["name"], contact=e["contact"],
            district=e.get("district"), languages=e.get("languages", []),
            verified_at=datetime.now(timezone.utc) if e.get("verified") else None)
    if commit:
        await session.commit()
    return len(entries)
