import pytest
from sqlalchemy import delete

from app.core.db import get_engine, get_sessionmaker
from app.models.facility import Facility
from app.services.facilities import FacilityService
from tests.test_identity import schema as _schema  # noqa: F401


@pytest.fixture(scope="module", autouse=True)
def schema(_schema):
    return _schema


@pytest.fixture(autouse=True)
async def _fresh(schema):
    await get_engine().dispose()
    async with get_sessionmaker()() as s:
        await s.execute(delete(Facility)); await s.commit()
    yield


async def _client():
    import httpx
    from app.main import app
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def test_seed_is_idempotent_and_nearby_sorts():
    async with get_sessionmaker()() as s:
        svc = FacilityService(s)
        n = await svc.seed()
        assert n > 0
        assert await svc.seed() == 0  # idempotent
        # near Kigali centre -> nearest first, with distances
        rows = await svc.list(lat=-1.95, lng=30.06, limit=5)
        dists = [r["distance_km"] for r in rows]
        assert all(d is not None for d in dists)
        assert dists == sorted(dists)
        # type filter
        pharm = await svc.list(type_="pharmacy")
        assert pharm and all(r["type"] == "pharmacy" for r in pharm)


async def test_endpoint_public_and_shape():
    async with get_sessionmaker()() as s:
        await FacilityService(s).seed()
    async with await _client() as c:
        r = await c.get("/v1/facilities?lat=-1.95&lng=30.06&limit=3")  # no auth header
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body, list) and len(body) <= 3
        assert {"id", "name", "type", "distance_km", "phone"} <= set(body[0].keys())
