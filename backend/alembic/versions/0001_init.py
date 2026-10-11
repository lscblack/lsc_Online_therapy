"""init schema

Revision ID: 0001
Revises:
"""
import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql as pg

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

JSONB = pg.JSONB
UUID = pg.UUID(as_uuid=True)

ENUMS = {
    "user_role": ["user", "reviewer", "admin"],
    "age_band": ["under15", "15_17", "18_19", "20_24", "25_plus", "undisclosed"],
    "doc_status": ["uploaded", "processing", "indexed", "failed"],
    "review_status": ["pending", "approved", "rejected"],
    "message_role": ["user", "assistant", "system"],
    "conversation_mode": ["text", "voice"],
}


def _enum(name: str) -> pg.ENUM:
    return pg.ENUM(*ENUMS[name], name=name, create_type=False)


def _ts(name: str, **kw) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), **kw)


def _pk() -> sa.Column:
    return sa.Column("id", UUID, primary_key=True)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    for name in ENUMS:
        _enum(name).create(op.get_bind(), checkfirst=True)

    op.create_table(
        "users",
        _pk(),
        sa.Column("anon_id", sa.String(128), nullable=False),
        sa.Column("email", sa.String(320)),
        sa.Column("password_hash", sa.String(255)),
        sa.Column("role", _enum("user_role"), nullable=False, server_default="user"),
        sa.Column("is_upgraded", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("recovery_hash", sa.String(255)),
        sa.Column("locale", sa.String(16), nullable=False, server_default="rw"),
        sa.Column("disabled", sa.Boolean, nullable=False, server_default=sa.text("false")),
        _ts("created_at", nullable=False, server_default=sa.func.now()),
        _ts("last_seen_at"),
        sa.UniqueConstraint("email", name="users_email_key"),
    )
    op.create_index("ix_users_anon_id", "users", ["anon_id"], unique=True)

    op.create_table(
        "profiles",
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("nickname", sa.String(64)),
        sa.Column("age_band", _enum("age_band"), nullable=False, server_default="undisclosed"),
        sa.Column("gender", sa.String(32)),
        sa.Column("pronouns", sa.String(32)),
        sa.Column("tone_pref", sa.String(32)),
        sa.Column("interests", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("sensitive_context_enc", sa.LargeBinary),
        sa.Column("consent", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        _ts("updated_at", nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "documents",
        _pk(),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("source_filename", sa.String(512)),
        sa.Column("language", sa.String(16)),
        sa.Column("topic_tags", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("status", _enum("doc_status"), nullable=False, server_default="uploaded"),
        sa.Column("review_status", _enum("review_status"), nullable=False, server_default="pending"),
        sa.Column("uploaded_by", UUID, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("reviewed_by", UUID, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("review_notes", sa.Text),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("checksum", sa.String(128)),
        _ts("created_at", nullable=False, server_default=sa.func.now()),
        _ts("indexed_at"),
    )
    op.create_index("ix_documents_checksum", "documents", ["checksum"])
    op.create_index("ix_documents_topic_tags_gin", "documents", ["topic_tags"],
                    postgresql_using="gin")

    op.create_table(
        "document_chunks",
        _pk(),
        sa.Column("document_id", UUID, sa.ForeignKey("documents.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("token_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("language", sa.String(16)),
        sa.Column("metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("embedding", Vector(768), nullable=False),
        sa.UniqueConstraint("document_id", "chunk_index", name="uq_chunk_doc_index"),
    )
    op.create_index("ix_document_chunks_document_id", "document_chunks", ["document_id"])
    op.create_index("ix_document_chunks_metadata_gin", "document_chunks", ["metadata"],
                    postgresql_using="gin")
    op.create_index(
        "ix_document_chunks_embedding_hnsw", "document_chunks", ["embedding"],
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )

    op.create_table(
        "conversations",
        _pk(),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mode", _enum("conversation_mode"), nullable=False, server_default="text"),
        sa.Column("language", sa.String(16)),
        _ts("created_at", nullable=False, server_default=sa.func.now()),
        _ts("last_message_at"),
    )
    op.create_index("ix_conversations_user_id", "conversations", ["user_id"])

    op.create_table(
        "messages",
        _pk(),
        sa.Column("conversation_id", UUID,
                  sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", _enum("message_role"), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("citations", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("safety_flags", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        _ts("created_at", nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])

    op.create_table(
        "referrals",
        _pk(),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("contact", sa.String(255), nullable=False),
        sa.Column("district", sa.String(128)),
        sa.Column("languages", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        _ts("verified_at"),
    )
    op.create_index("ix_referrals_category", "referrals", ["category"])

    op.create_table(
        "facilities",
        _pk(),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("type", sa.String(64), nullable=False),
        sa.Column("lat", sa.Float),
        sa.Column("lng", sa.Float),
        sa.Column("district", sa.String(128)),
        sa.Column("services", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("hours", sa.String(255)),
        _ts("verified_at"),
    )
    op.create_index("ix_facilities_district", "facilities", ["district"])

    op.create_table(
        "audit_log",
        _pk(),
        sa.Column("actor_id", UUID, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("target", sa.String(255)),
        sa.Column("metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        _ts("at", nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_audit_log_actor_id", "audit_log", ["actor_id"])
    op.create_index("ix_audit_log_action", "audit_log", ["action"])


def downgrade() -> None:
    for t in ("audit_log", "facilities", "referrals", "messages", "conversations",
              "document_chunks", "documents", "profiles", "users"):
        op.drop_table(t)
    for name in ENUMS:
        _enum(name).drop(op.get_bind(), checkfirst=True)
