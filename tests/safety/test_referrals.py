import pytest
from sqlalchemy import delete, select

from app.core.db import get_engine, get_sessionmaker
from app.models import Referral
from app.safety.referrals import lookup, seed_referrals
from tests.test_identity import schema as _schema  # noqa: F401


@pytest.fixture(scope="module", autouse=True)
def schema(_schema):
    return _schema


@pytest.fixture(autouse=True)
async def _fresh_pool(schema):
    await get_engine().dispose()
    yield


@pytest.fixture
async def session():
    async with get_sessionmaker()() as s:
        await s.execute(delete(Referral))
        await s.commit()
        yield s
        await s.rollback()
        await s.execute(delete(Referral))
        await s.commit()


async def test_seed_idempotent_and_unverified(session):
    n1 = await seed_referrals(session)
    n2 = await seed_referrals(session)
    assert n1 == n2 > 0
    rows = (await session.execute(select(Referral))).scalars().all()
    assert len(rows) == n1
    assert all(r.verified_at is None for r in rows)
    assert all("PLACEHOLDER" in r.contact.upper() for r in rows)
    cats = {r.category for r in rows}
    assert {"crisis", "gbv", "clinic", "emergency"} <= cats


async def test_lookup_by_category_and_district(session):
    await seed_referrals(session)
    gbv = await lookup(session, "gbv")
    assert gbv and all(r.category == "gbv" for r in gbv)
    assert await lookup(session, "nonexistent") == []
    local = await lookup(session, "clinic", district="Gasabo")
    assert local and local[0].district in ("Gasabo", None)
