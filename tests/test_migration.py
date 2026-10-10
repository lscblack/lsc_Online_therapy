import asyncio
from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings
from app.models import Base

ROOT = Path(__file__).resolve().parent.parent

TABLES = {
    "users", "profiles", "documents", "document_chunks", "conversations",
    "messages", "referrals", "facilities", "audit_log",
}
ENUM_TYPES = {
    "user_role", "age_band", "doc_status", "review_status", "message_role",
    "conversation_mode",
}


def _alembic_cfg() -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    return cfg


def _query(sql: str):
    async def run():
        engine = create_async_engine(get_settings().database_url)
        try:
            async with engine.connect() as conn:
                return (await conn.execute(text(sql))).all()
        finally:
            await engine.dispose()

    return asyncio.run(run())


def _diff():
    async def run():
        engine = create_async_engine(get_settings().database_url)
        try:
            async with engine.connect() as conn:
                def f(sync_conn):
                    ctx = MigrationContext.configure(sync_conn, opts={"compare_type": True})
                    return compare_metadata(ctx, Base.metadata)
                return await conn.run_sync(f)
        finally:
            await engine.dispose()

    return asyncio.run(run())


def test_upgrade_creates_tables_and_vector():
    cfg = _alembic_cfg()
    command.downgrade(cfg, "base")
    try:
        command.upgrade(cfg, "head")
        assert _query("select extname from pg_extension where extname='vector'")
        tables = {r[0] for r in _query(
            "select tablename from pg_tables where schemaname='public'")}
        assert TABLES <= tables
        defs = [r[0] for r in _query(
            "select indexdef from pg_indexes where tablename='document_chunks'")]
        assert any("hnsw" in d and "embedding" in d and "vector_cosine_ops" in d
                   for d in defs)
        assert any("gin" in d and "metadata" in d for d in defs)
        docidx = [r[0] for r in _query(
            "select indexdef from pg_indexes where tablename='documents'")]
        assert any("gin" in d and "topic_tags" in d for d in docidx)

        types = {r[0] for r in _query(
            "select typname from pg_type where typtype='e'")}
        assert ENUM_TYPES <= types

        dim = _query(
            "select atttypmod from pg_attribute where attrelid='document_chunks'::regclass "
            "and attname='embedding'")
        assert dim[0][0] == 768

        cols = {r[0] for r in _query(
            "select column_name from information_schema.columns where table_name='users'")}
        assert {"email", "password_hash"} <= cols

        assert _diff() == []
    finally:
        command.downgrade(cfg, "base")
    left = {r[0] for r in _query(
        "select tablename from pg_tables where schemaname='public'")}
    assert not (TABLES & left)
