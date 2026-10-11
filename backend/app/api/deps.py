import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.security import ACCESS, TokenError, decode_token
from app.models import User
from app.models.user import UserRole
from app.repositories.users import UserRepository

_bearer = HTTPBearer(auto_error=False)


def _unauthorized(detail: str = "Not authenticated") -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detail,
                         headers={"WWW-Authenticate": "Bearer"})


async def user_from_token(token: str, session: AsyncSession, expected_type: str) -> User:
    try:
        claims = decode_token(token, expected_type=expected_type)
        sub = claims["sub"]
        if not isinstance(sub, str):
            raise ValueError("sub must be a string")
        user_id = uuid.UUID(sub)
    except (TokenError, ValueError, TypeError, AttributeError, KeyError) as e:
        raise _unauthorized("Invalid or expired token") from e
    user = await UserRepository(session).get_by_id(user_id)
    if user is None or user.disabled:
        raise _unauthorized("Invalid or expired token")
    return user


async def current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: AsyncSession = Depends(get_session),
) -> User:
    if creds is None:
        raise _unauthorized()
    return await user_from_token(creds.credentials, session, ACCESS)


def require_role(*roles: UserRole | str):
    allowed = {UserRole(r) for r in roles}

    async def checker(user: User = Depends(current_user)) -> User:
        # Role comes from the DB row, never from the token claim.
        if user.role not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient role")
        return user

    return checker
