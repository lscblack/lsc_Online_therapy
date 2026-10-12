"""Nearby health facilities.

GET /v1/facilities  -> list of hospitals/clinics/health centres/pharmacies. Public (no auth) so
the mobile app can sync the whole list for offline use. Optional query:
  type=hospital|clinic|health_center|pharmacy
  lat, lng  -> adds distance_km and sorts nearest-first
  limit     -> cap (default 200)
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.schemas.facility import FacilityOut
from app.services.facilities import FacilityService

router = APIRouter(prefix="/v1/facilities", tags=["facilities"])


@router.get("", response_model=list[FacilityOut])
async def list_facilities(
    type: str | None = Query(None),
    lat: float | None = Query(None, ge=-90, le=90),
    lng: float | None = Query(None, ge=-180, le=180),
    limit: int = Query(200, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
) -> list[FacilityOut]:
    rows = await FacilityService(session).list(type, lat, lng, limit)
    return [FacilityOut(**r) for r in rows]
