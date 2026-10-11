import builtins
import uuid
from datetime import datetime

from sqlalchemy import Select, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import DocStatus, Document, DocumentChunk, ReviewStatus


class DocumentRepository:
    """Repositories flush only; the calling service owns the commit."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_document(self, **fields) -> Document:
        doc = Document(**fields)
        self.session.add(doc)
        await self.session.flush()
        await self.session.refresh(doc)
        return doc

    async def get(self, document_id: uuid.UUID) -> Document | None:
        return await self.session.get(Document, document_id)

    async def list(self, review_status: ReviewStatus | None = None,
                   status: DocStatus | None = None, limit: int = 100,
                   offset: int = 0) -> builtins.list[Document]:
        stmt = select(Document).order_by(Document.created_at.desc(), Document.id)
        if review_status is not None:
            stmt = stmt.where(Document.review_status == review_status)
        if status is not None:
            stmt = stmt.where(Document.status == status)
        res = await self.session.execute(stmt.limit(limit).offset(offset))
        return list(res.scalars())

    async def add_chunks(self, document_id: uuid.UUID, rows: builtins.list[dict]) -> builtins.list[DocumentChunk]:
        """rows: dicts with chunk_index, content, token_count, language, meta, embedding."""
        chunks = [DocumentChunk(document_id=document_id, **r) for r in rows]
        self.session.add_all(chunks)
        await self.session.flush()
        return chunks

    async def delete_chunks(self, document_id: uuid.UUID) -> None:
        await self.session.execute(
            delete(DocumentChunk).where(DocumentChunk.document_id == document_id))
        await self.session.flush()

    async def set_status(self, doc: Document, status: DocStatus, *,
                         indexed_at: datetime | None = None,
                         review_notes: str | None = None) -> Document:
        doc.status = status
        if indexed_at is not None:
            doc.indexed_at = indexed_at
        if review_notes is not None:
            doc.review_notes = review_notes
        await self.session.flush()
        await self.session.refresh(doc)
        return doc

    async def set_review(self, doc: Document, status: ReviewStatus,
                         reviewer: uuid.UUID | None = None,
                         notes: str | None = None) -> Document:
        doc.review_status = status
        doc.reviewed_by = reviewer
        doc.review_notes = notes
        await self.session.flush()
        await self.session.refresh(doc)
        return doc

    @staticmethod
    def approved_chunks_stmt() -> Select:
        """SELECT DocumentChunk joined to Document, restricted to retrievable chunks:
        review_status == approved AND status == indexed. Task 7 retrieval MUST build on
        this (add .order_by(embedding.cosine_distance(q)).limit(k), extra filters)."""
        return (select(DocumentChunk)
                .join(Document, Document.id == DocumentChunk.document_id)
                .where(Document.review_status == ReviewStatus.approved,
                       Document.status == DocStatus.indexed))
