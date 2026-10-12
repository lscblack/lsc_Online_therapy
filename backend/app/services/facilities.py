import math

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.facilities_seed import FACILITIES
from app.models.facility import Facility

VALID_TYPES = {"hospital", "clinic", "health_center", "pharmacy"}


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


class FacilityService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def seed(self) -> int:
        """Insert the starter dataset if the table is empty. Idempotent."""
        count = (await self.session.execute(select(func.count()).select_from(Facility))).scalar_one()
        if count:
            return 0
        for (name, typ, district, lat, lng, phone, address, hours, services) in FACILITIES:
            self.session.add(Facility(
                name=name, type=typ, district=district, lat=lat, lng=lng,
                phone=phone, address=address, hours=hours, services=services))
        await self.session.commit()
        return len(FACILITIES)

    async def list(self, type_: str | None = None, lat: float | None = None,
                   lng: float | None = None, limit: int = 100) -> list[dict]:
        """All facilities (optionally one type). When lat/lng are given, add distance_km and sort
        nearest-first; otherwise sorted by name. Distances are computed in Python (small dataset)."""
        stmt = select(Facility)
        if type_ in VALID_TYPES:
            stmt = stmt.where(Facility.type == type_)
        rows = list((await self.session.execute(stmt)).scalars())
        out = []
        for f in rows:
            d = None
            if lat is not None and lng is not None and f.lat is not None and f.lng is not None:
                d = round(_haversine_km(lat, lng, f.lat, f.lng), 2)
            out.append({
                "id": str(f.id), "name": f.name, "type": f.type, "district": f.district,
                "lat": f.lat, "lng": f.lng, "phone": f.phone, "address": f.address,
                "hours": f.hours, "services": f.services or [], "distance_km": d,
            })
        if lat is not None and lng is not None:
            out.sort(key=lambda x: (x["distance_km"] is None, x["distance_km"] if x["distance_km"] is not None else 1e9))
        else:
            out.sort(key=lambda x: x["name"])
        return out[:limit]
