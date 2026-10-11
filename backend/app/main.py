import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
        log.warning("Referral seeding skipped (%s); if the schema is missing run "
                    "`alembic upgrade head`", type(e).__name__)
        log.debug("Referral seeding error detail: %s", e)
        return 0


async def bootstrap_default_admin_on_startup() -> bool:
    """Create the first admin from DEFAULT_ADMIN_EMAIL/PASSWORD if set and absent.

    Idempotent and non-blocking: a bad/missing config or DB never stops startup.
    Returns True only when a new admin row was created this call.
    """
    from app.core.config import get_settings
    from app.core.security import ahash_secret
    from app.models.user import UserRole
    from app.repositories.users import UserRepository

    settings = get_settings()
    email = (settings.default_admin_email or "").strip().lower()
    password = settings.default_admin_password or ""
    if not email or not password:
        return False
    if "@" not in email:
        log.warning("DEFAULT_ADMIN_EMAIL is not a valid email; skipping admin bootstrap")
        return False
    try:
        async with get_sessionmaker()() as session:
            repo = UserRepository(session)
            if await repo.get_by_email(email):
                return False
            import secrets
            await repo.create(anon_id=f"admin-{secrets.token_urlsafe(16)}", email=email,
                              password_hash=await ahash_secret(password), role=UserRole.admin)
            await session.commit()
        log.info("Bootstrapped default admin %s", email)
        return True
    except Exception as e:  # noqa: BLE001
        log.warning("Default-admin bootstrap skipped (%s); if the schema is missing run "
                    "`alembic upgrade head`", type(e).__name__)
        log.debug("Default-admin bootstrap error detail: %s", e)
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    await seed_referrals_on_startup()
    await bootstrap_default_admin_on_startup()
    from app.core.config import get_settings
    from app.realtime import reaper, signaling
    task = asyncio.ensure_future(reaper.run_reaper(
        signaling.registry, interval=get_settings().realtime_reaper_interval_seconds))
    try:
        yield
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        try:
            await signaling.registry.close_all()
        except Exception:  # noqa: BLE001
            log.exception("closing live sessions on shutdown failed")


app = FastAPI(
    title="Ubuzima",
    version="0.1.0",
    description="AI SRHR health-information navigator for Rwandan youth (EN/RW). "
                "Errors use {\"error\": {\"code\", \"message\"}}. Send Accept-Language: en|rw.",
    lifespan=lifespan,
)
install_error_handlers(app)
from app.core.config import get_settings as _get_settings  # noqa: E402

app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_settings().cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "Accept-Language"],
)
app.include_router(health.router)
app.include_router(admin.router)
app.include_router(identity.router)
app.include_router(profile.router)
app.include_router(chat.router)
app.include_router(voice.router)
app.include_router(live.router)
