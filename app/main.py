import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1 import admin, chat, health, identity, live, profile, voice
from app.core.db import get_sessionmaker
from app.core.errors import install_error_handlers
from app.safety.referrals import seed_referrals

log = logging.getLogger(__name__)


async def seed_referrals_on_startup() -> int:
    """Idempotent referral seed; never blocks startup (e.g. DB not migrated yet)."""
    try:
        async with get_sessionmaker()() as session:
            return await seed_referrals(session)
    except Exception as e:  # noqa: BLE001
        log.warning("Referral seeding skipped (%s: run `alembic upgrade head`?)",
                    type(e).__name__)
        return 0


@asynccontextmanager
async def lifespan(app: FastAPI):
    await seed_referrals_on_startup()
    yield


app = FastAPI(
    title="Ubuzima",
    version="0.1.0",
    description="AI SRHR health-information navigator for Rwandan youth (EN/RW). "
                "Errors use {\"error\": {\"code\", \"message\"}}. Send Accept-Language: en|rw.",
    lifespan=lifespan,
)
install_error_handlers(app)
app.include_router(health.router)
app.include_router(admin.router)
app.include_router(identity.router)
app.include_router(profile.router)
app.include_router(chat.router)
app.include_router(voice.router)
app.include_router(live.router)
