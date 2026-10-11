import asyncio
import builtins
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.models.document import DocStatus, Document, ReviewStatus
from app.providers.base import EmbeddingProvider
from app.repositories.audit import AuditRepository
from app.repositories.documents import DocumentRepository
from app.repositories.users import UserRepository
from app.services.ingestion import IngestionService


class AdminService:
    """Admin/reviewer operations. Every state change writes an AuditLog row.
    Review/reindex/ingest commit inside IngestionService, so their audit row is committed
    immediately after (separate transaction); delete/disable are atomic with their audit."""

    def __init__(self, session: AsyncSession, embeddings: EmbeddingProvider | None = None):
        self.session = session
        self.ingestion = IngestionService(session, embeddings)
        self.docs = DocumentRepository(session)
        self.users = UserRepository(session)
        self.audit = AuditRepository(session)

    async def _audit(self, actor: User, action: str, target: str, meta: dict | None = None,
                     *, refresh=None) -> None:
        await self.audit.record(actor.id, action, target, meta)
        await self.session.commit()
        if refresh is not None:  # commit expires loaded attributes; reload for the response
            await self.session.refresh(refresh)

    async def upload_document(self, actor: User, title: str, filename: str | None, data: bytes,
                              language: str | None = None,
                              topic_tags: builtins.list[str] | None = None) -> Document:
        doc = await self.ingestion.create_document(
            title, filename, data, language=language, uploaded_by=actor.id,
            topic_tags=topic_tags)
        doc_id = doc.id
        doc = await self.ingestion.ingest(doc_id)  # failures end as status=failed, not raised
        await self._audit(actor, "document.upload", str(doc_id),
                          {"title": title, "status": doc.status.value}, refresh=doc)
        return doc

    async def list_documents(self, review_status: ReviewStatus | None = None,
                             status: DocStatus | None = None, limit: int = 100,
                             offset: int = 0) -> builtins.list[Document]:
        return await self.docs.list(review_status, status, limit, offset)

    async def get_document(self, document_id: uuid.UUID) -> Document:
        doc = await self.docs.get(document_id)
        if doc is None:
            raise LookupError(f"document {document_id} not found")
        return doc

    async def review_document(self, actor: User, document_id: uuid.UUID, status: ReviewStatus,
                              notes: str | None = None) -> Document:
        doc = await self.ingestion.set_review(document_id, status, actor.id, notes)
        await self._audit(actor, "document.review", str(document_id),
                          {"status": status.value, "notes": notes}, refresh=doc)
        return doc

    async def reindex_document(self, actor: User, document_id: uuid.UUID) -> Document:
        doc = await self.ingestion.reindex(document_id)
        await self._audit(actor, "document.reindex", str(document_id),
                          {"status": doc.status.value, "version": doc.version}, refresh=doc)
        return doc

    async def delete_document(self, actor: User, document_id: uuid.UUID) -> None:
        doc = await self.get_document(document_id)
        title = doc.title
        await self.docs.delete_chunks(doc.id)
        await self.session.delete(doc)
        await self.audit.record(actor.id, "document.delete", str(document_id),
                                {"title": title})
        await self.session.commit()
        # File removed only after the DB commit succeeds.
        await asyncio.to_thread(self.ingestion._path(document_id).unlink, True)

    async def list_users(self, limit: int = 100, offset: int = 0) -> builtins.list[User]:
        res = await self.session.execute(
            select(User).order_by(User.created_at.desc(), User.id).limit(limit).offset(offset))
        return list(res.scalars())

    async def disable_user(self, actor: User, user_id: uuid.UUID) -> User:
        user = await self.users.get_by_id(user_id)
        if user is None:
            raise LookupError(f"user {user_id} not found")
        await self.users.update(user, disabled=True)
        await self.audit.record(actor.id, "user.disable", str(user_id))
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def list_audit(self, limit: int = 100, offset: int = 0):
        return await self.audit.list(limit, offset)
