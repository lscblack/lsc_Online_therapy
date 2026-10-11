import os

import httpx
import pytest
from pydantic_settings import BaseSettings, SettingsConfigDict


class _TestEnv(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    test_database_url: str | None = None
    database_url: str | None = None


_env = _TestEnv()
_url = _env.test_database_url or _env.database_url or ""
if not _url.rsplit("/", 1)[-1].endswith("_test"):
    pytest.exit(
        "Refusing to run: set TEST_DATABASE_URL (or DATABASE_URL) to a database "
        f"whose name ends in '_test' (got {_url.rsplit('/', 1)[-1]!r}).",
        returncode=2,
    )
os.environ["DATABASE_URL"] = _url

from app.main import app  # noqa: E402


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    from app.core import ratelimit
    ratelimit.reset()
    yield
