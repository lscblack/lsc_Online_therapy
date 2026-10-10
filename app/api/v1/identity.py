from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, user_from_token
from app.core.db import get_session
from app.core.security import REFRESH
from app.models import User
from app.schemas.identity import (
    AnonSession,
    RecoverRequest,
    RefreshRequest,
    TokenPair,
    UpgradeRequest,
    UpgradeResponse,
)
from app.services.identity import AlreadyUpgraded, IdentityService, InvalidCredentials

router = APIRouter(prefix="/v1/identity", tags=["identity"])


def _bad_creds() -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")


@router.post("/anon", response_model=AnonSession)
async def anon(session: AsyncSession = Depends(get_session)) -> AnonSession:
    user, t = await IdentityService(session).bootstrap_anon()
    return AnonSession(access_token=t.access_token, refresh_token=t.refresh_token,
                       anon_id=user.anon_id)


@router.post("/upgrade", response_model=UpgradeResponse)
async def upgrade(body: UpgradeRequest, user: User = Depends(current_user),
                  session: AsyncSession = Depends(get_session)) -> UpgradeResponse:
    try:
        user = await IdentityService(session).upgrade(user, body.passphrase)
    except AlreadyUpgraded as e:
        raise HTTPException(status.HTTP_409_CONFLICT, "Recovery passphrase already set") from e
    except InvalidCredentials as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed") from e
    return UpgradeResponse(is_upgraded=user.is_upgraded)


@router.post("/recover", response_model=AnonSession)
async def recover(body: RecoverRequest,
                  session: AsyncSession = Depends(get_session)) -> AnonSession:
    try:
        user, t = await IdentityService(session).recover(body.anon_id, body.passphrase)
    except InvalidCredentials as e:
        raise _bad_creds() from e
    return AnonSession(access_token=t.access_token, refresh_token=t.refresh_token,
                       anon_id=user.anon_id)


@router.post("/refresh", response_model=TokenPair)
async def refresh(body: RefreshRequest,
                  session: AsyncSession = Depends(get_session)) -> TokenPair:
    user = await user_from_token(body.refresh_token, session, REFRESH)
    t = await IdentityService(session).refresh(user)
    return TokenPair(access_token=t.access_token, refresh_token=t.refresh_token)
