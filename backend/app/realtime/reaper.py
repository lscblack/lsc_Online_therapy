"""Background reaper for live sessions: closes idle, over-long, and never-attached sessions.

Deadlines (all on the monotonic clock used by LiveEntry):
* idle:     now - last_activity > idle_s
* max:      now - created_at    > max_s
* unattached: not ws_attached and now - created_at > attach_grace_s
Per-entry failures are logged and never stop the pass or the loop.
"""
import asyncio
import logging
import time
from collections.abc import Callable

from app.core.config import get_settings

logger = logging.getLogger(__name__)


async def reap_once(registry, *, now: float, idle_s: float, max_s: float,
                    attach_grace_s: float) -> int:
    """One pass. Returns the number of sessions that were due (close attempted)."""
    due = []
    for e in registry.all():
        try:
            if (now - e.last_activity > idle_s or now - e.created_at > max_s
                    or (not e.ws_attached and now - e.created_at > attach_grace_s)):
                due.append(e)
        except Exception:  # noqa: BLE001
            logger.exception("reaper: bad session entry")
    for e in due:
        try:
            await e.close()
        except Exception:  # noqa: BLE001
            logger.exception("reaper: closing session %s failed", getattr(e, "id", "?"))
    return len(due)


async def run_reaper(registry, *, interval: float = 5.0, clock: Callable[[], float] = time.monotonic,
                     idle_s: float | None = None, max_s: float | None = None,
                     attach_grace_s: float | None = None) -> None:
    """Loop forever; only cancellation ends it."""
    while True:
        try:
            s = get_settings()
            n = await reap_once(
                registry, now=clock(),
                idle_s=s.realtime_idle_seconds if idle_s is None else idle_s,
                max_s=s.realtime_max_session_seconds if max_s is None else max_s,
                attach_grace_s=(s.realtime_ws_attach_grace_seconds
                                if attach_grace_s is None else attach_grace_s))
            if n:
                logger.info("reaper closed %d live session(s)", n)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            logger.exception("reaper pass failed; continuing")
        await asyncio.sleep(interval)
