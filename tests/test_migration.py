import asyncio

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings

TABLES = {
    "users", "profiles", "documents", "document_chunks", "conversations",
    "messages", "referrals", "facilities", "audit_log",
}


def _query(sql: str):
    async def run():
        engine = create_async_engine(get_settings().database_url)
        try:
            async with engine.connect() as conn:
                return (await conn.execute(text(sql))).all()
        finally:
            await engine.dispose()

    return asyncio.run(run())


def test_upgrade_creates_tables_and_vector():
    cfg = Config("alembic.ini")
    command.downgrade(cfg, "base")
    try:
        command.upgrade(cfg, "head")
        ext = _query("select extname from pg_extension where extname='vector'")
        assert ext
        tables = {r[0] for r in _query(
            "select tablename from pg_tables where schemaname='public'")}
        assert TABLES <= tables
        idx = _query(
            "select indexdef from pg_indexes where tablename='document_chunks'")
        defs = [r[0] for r in idx]
        assert any("hnsw" in d and "embedding" in d and "vector_cosine_ops" in d
                   for d in defs)
        assert any("gin" in d and "metadata" in d for d in defs)
        docidx = [r[0] for r in _query(
            "select indexdef from pg_indexes where tablename='documents'")]
        assert any("gin" in d and "topic_tags" in d for d in docidx)
    finally:
        command.downgrade(cfg, "base")
    left = {r[0] for r in _query(
        "select tablename from pg_tables where schemaname='public'")}
    assert not (TABLES & left)
