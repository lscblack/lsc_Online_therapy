import os
import subprocess
import sys
from pathlib import Path


async def test_health_ok(client):
    r = await client.get("/v1/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


async def test_ready_checks_db(client):
    r = await client.get("/v1/ready")
    assert r.status_code == 200


async def test_ready_returns_503_when_db_down(client):
    from sqlalchemy.exc import OperationalError

    from app.core.db import get_session
    from app.main import app

    class BrokenSession:
        async def execute(self, *a, **k):
            raise OperationalError("SELECT 1", {}, Exception("down"))

    async def broken():
        yield BrokenSession()

    app.dependency_overrides[get_session] = broken
    try:
        r = await client.get("/v1/ready")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 503


def test_app_imports_with_only_db_settings(tmp_path):
    root = Path(__file__).parent.parent
    env = {
        "DATABASE_URL": "postgresql+asyncpg://u:p@127.0.0.1:1/x_test",
        "PATH": os.environ["PATH"],
        "PYTHONPATH": str(root),
    }
    r = subprocess.run(
        [sys.executable, "-c", "import app.main"],
        cwd=tmp_path, env=env, capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
