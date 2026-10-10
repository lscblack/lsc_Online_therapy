from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.core import crypto
from app.core.db import get_session
from app.models import User
from app.schemas.profile import ProfileOut, ProfileUpdate
from app.services.profile import ProfileService

router = APIRouter(prefix="/v1/profile", tags=["profile"])


@router.get("", response_model=ProfileOut)
async def get_profile(user: User = Depends(current_user),
                      session: AsyncSession = Depends(get_session)) -> ProfileOut:
    svc = ProfileService(session)
    profile = await svc.get(user)
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No profile")
    return _out(svc, profile)


@router.put("", response_model=ProfileOut)
async def put_profile(body: ProfileUpdate, user: User = Depends(current_user),
                      session: AsyncSession = Depends(get_session)) -> ProfileOut:
    svc = ProfileService(session)
    try:
        profile = await svc.upsert(user, body)
    except crypto.EncryptionKeyError as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "Encryption unavailable") from e
    return _out(svc, profile)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def wipe_profile(user: User = Depends(current_user),
                       session: AsyncSession = Depends(get_session)) -> Response:
    await ProfileService(session).wipe(user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _out(svc: ProfileService, profile) -> ProfileOut:
    try:
        return svc.to_out(profile)
    except (crypto.EncryptionKeyError, crypto.DecryptionError) as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "Sensitive context unavailable") from e
