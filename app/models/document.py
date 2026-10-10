import enum
import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    DateTime, Enum, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at_col, uuid_pk

EMBEDDING_DIM = 768


class DocStatus(enum.StrEnum):
    uploaded = "uploaded"
    processing = "processing"
    indexed = "indexed"
    failed = "failed"


class ReviewStatus(enum.StrEnum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        Index("ix_documents_topic_tags_gin", "topic_tags", postgresql_using="gin"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    title: Mapped[str] = mapped_column(String(512))
    source_filename: Mapped[str | None] = mapped_column(String(512))
    language: Mapped[str | None] = mapped_column(String(16))
    topic_tags: Mapped[Any] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    status: Mapped[DocStatus] = mapped_column(
        Enum(DocStatus, name="doc_status"), default=DocStatus.uploaded,
        server_default=DocStatus.uploaded.value)
    review_status: Mapped[ReviewStatus] = mapped_column(
        Enum(ReviewStatus, name="review_status"), default=ReviewStatus.pending,
        server_default=ReviewStatus.pending.value)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    review_notes: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    checksum: Mapped[str | None] = mapped_column(String(128), index=True)
    created_at: Mapped[datetime] = created_at_col()
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_chunk_doc_index"),
        Index(
            "ix_document_chunks_embedding_hnsw", "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("ix_document_chunks_metadata_gin", "metadata", postgresql_using="gin"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    token_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    language: Mapped[str | None] = mapped_column(String(16))
    # DB column is "metadata"; attribute is `meta` because `metadata` is reserved by SQLAlchemy.
    meta: Mapped[Any] = mapped_column(
        "metadata", JSONB, default=dict, server_default=text("'{}'::jsonb"))
    embedding: Mapped[Any] = mapped_column(Vector(EMBEDDING_DIM))
