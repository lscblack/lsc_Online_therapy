from pydantic import BaseModel


class FacilityOut(BaseModel):
    id: str
    name: str
    type: str
    district: str | None
    lat: float | None
    lng: float | None
    phone: str | None
    address: str | None
    hours: str | None
    services: list[str]
    distance_km: float | None = None
