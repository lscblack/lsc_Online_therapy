"""JWT (PyJWT, HS256) and argon2 secret hashing. Never log tokens or secrets."""
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import get_settings

ACCESS = "access"
REFRESH = "refresh"

_hasher = PasswordHasher()


class TokenError(Exception):
    """Base class for token problems."""


class TokenExpiredError(TokenError):
    pass


class TokenInvalidError(TokenError):
    pass


def hash_secret(raw: str) -> str:
    return _hasher.hash(raw)


def verify_secret(raw: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, raw)
    except (VerificationError, InvalidHashError):
        return False


def _secret() -> str:
    secret = get_settings().jwt_secret
    if not secret:
        raise RuntimeError("JWT_SECRET is not configured; refusing to sign/verify tokens")
    return secret


def _encode(sub: str, token_type: str, ttl: timedelta, extra: dict[str, Any]) -> str:
    now = datetime.now(UTC)
    claims = {
        **extra,
        "sub": sub,
        "type": token_type,
        "iat": now,
        "exp": now + ttl,
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(claims, _secret(), algorithm=get_settings().jwt_algorithm)


def create_access_token(sub: str, role: str, **claims: Any) -> str:
    ttl = timedelta(minutes=get_settings().access_token_ttl_min)
    return _encode(sub, ACCESS, ttl, {**claims, "role": str(role)})


def create_refresh_token(sub: str) -> str:
    return _encode(sub, REFRESH, timedelta(days=get_settings().refresh_token_ttl_days), {})


def decode_token(token: str, expected_type: str | None = None) -> dict[str, Any]:
    """Verify signature/expiry and return claims.

    Raises TokenExpiredError / TokenInvalidError. Algorithm is pinned (no alg=none or
    algorithm confusion); exp and sub are mandatory.
    """
    secret = _secret()
    try:
        claims = jwt.decode(
            token, secret, algorithms=[get_settings().jwt_algorithm],
            options={"require": ["exp", "sub", "type"]},
        )
    except jwt.ExpiredSignatureError as e:
        raise TokenExpiredError("token expired") from e
    except jwt.PyJWTError as e:
        raise TokenInvalidError("invalid token") from e
    if expected_type is not None and claims.get("type") != expected_type:
        raise TokenInvalidError("wrong token type")
    return claims
