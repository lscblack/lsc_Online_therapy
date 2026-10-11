"""Tiny in-process sliding-window rate limiter (no dependency).

MVP caveat: state is per process, so limits are NOT shared across uvicorn workers/replicas.
Use a shared store (e.g. Redis) or a gateway limiter when scaling out.
"""
import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable

from fastapi import HTTPException, Request, status

from app.core.config import get_settings

_hits: dict[str, deque[float]] = defaultdict(deque)
_lock = threading.Lock()
WINDOW = 60.0
_MAX_KEYS = 50_000


def reset() -> None:
    with _lock:
        _hits.clear()


def _check(key: str, limit: int) -> float | None:
    """Record a hit; return seconds to wait if over the limit, else None."""
    now = time.monotonic()
    with _lock:
        if len(_hits) > _MAX_KEYS:
            for k in [k for k, q in _hits.items() if not q or now - q[-1] > WINDOW]:
                del _hits[k]
        q = _hits[key]
        while q and now - q[0] >= WINDOW:
            q.popleft()
        if len(q) >= limit:
            return max(1.0, WINDOW - (now - q[0]))
        q.append(now)
        return None


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _key_from_token(request: Request) -> str:
    """Per-identity key from the bearer token (unverified: only used as a bucket label, auth
    still happens in current_user); falls back to IP."""
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer ") and len(auth) > 20:
        import hashlib
        return "tok:" + hashlib.sha256(auth[7:].encode()).hexdigest()[:16]
    return "ip:" + _client_ip(request)


def rate_limit(scope: str, setting: str, per_identity: bool = False) -> Callable:
    """FastAPI dependency factory. `setting` names a Settings int (requests per minute);
    <= 0 disables."""
    async def dep(request: Request) -> None:
        if not get_settings().rate_limit_enabled:
            return
        limit = int(getattr(get_settings(), setting))
        if limit <= 0:
            return
        who = _key_from_token(request) if per_identity else "ip:" + _client_ip(request)
        wait = _check(f"{scope}:{who}", limit)
        if wait is not None:
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many requests",
                                headers={"Retry-After": str(int(wait) + 1)})
    return dep
