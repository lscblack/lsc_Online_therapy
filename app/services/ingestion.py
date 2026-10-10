import asyncio
import hashlib
import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.document import DocStatus, Document, ReviewStatus
from app.providers.base import EmbeddingProvider
from app.providers.factory import get_embeddings
from app.rag.chunking import chunk
from app.rag.extract import ExtractionError, extract_text
from app.repositories.documents import DocumentRepository

log = logging.getLogger(__name__)
EMBED_BATCH = 32


class IngestionService:
    def __init__(self, session: AsyncSession, embeddings: EmbeddingProvider | None = None):
        self.session = session
        self.repo = DocumentRepository(session)
        self._embeddings = embeddings

    @property
    def embeddings(self) -> EmbeddingProvider:
        if self._embeddings is None:
            self._embeddings = get_embeddings()
        return self._embeddings

    @staticmethod
    def _path(document_id: uuid.UUID) -> Path:
        return Path(get_settings().storage_dir) / f"{document_id}.pdf"

    async def _get(self, document_id: uuid.UUID) -> Document:
        doc = await self.repo.get(document_id)
        if doc is None:
            raise LookupError(f"document {document_id} not found")
        return doc

    async def create_document(self, title: str, source_filename: str | None, data: bytes,
                              language: str | None = None, uploaded_by: uuid.UUID | None = None,
                              topic_tags: list[str] | None = None) -> Document:
        doc = await self.repo.create_document(
            title=title, source_filename=source_filename, language=language,
            uploaded_by=uploaded_by, topic_tags=topic_tags or [],
            status=DocStatus.uploaded, review_status=ReviewStatus.pending,
            checksum=hashlib.sha256(data).hexdigest())
        path = self._path(doc.id)
        try:
            await asyncio.to_thread(self._write, path, data)
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            path.unlink(missing_ok=True)
            raise
        return doc

    @staticmethod
    def _write(path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    async def ingest(self, document_id: uuid.UUID) -> Document:
        """uploaded -> processing -> indexed | failed. Chunks are only written after
        extraction, chunking and embedding all succeed, so a failure leaves none."""
        doc = await self._get(document_id)
        await self.repo.delete_chunks(doc.id)
        await self.repo.set_status(doc, DocStatus.processing)
        await self.session.commit()
        try:
            data = await asyncio.to_thread(self._path(doc.id).read_bytes)
            pages = await asyncio.to_thread(extract_text, data)
            chunks = chunk(pages)
            if not chunks:
                raise ExtractionError("no chunks produced")
            vectors: list[list[float]] = []
            for i in range(0, len(chunks), EMBED_BATCH):
                batch = [c.content for c in chunks[i:i + EMBED_BATCH]]
                vectors.extend(await self.embeddings.embed(batch, "passage"))
            if len(vectors) != len(chunks):
                raise RuntimeError("embedding count mismatch")
            await self.repo.add_chunks(doc.id, [
                {"chunk_index": c.index, "content": c.content, "token_count": c.token_count,
                 "language": doc.language, "meta": c.meta, "embedding": v}
                for c, v in zip(chunks, vectors, strict=True)])
            await self.repo.set_status(doc, DocStatus.indexed, indexed_at=datetime.now(UTC))
            await self.session.commit()
        except Exception as e:
            await self.session.rollback()
            if not isinstance(e, ExtractionError):
                log.exception("ingestion failed for %s", document_id)
            doc = await self._get(document_id)
            await self.repo.delete_chunks(doc.id)
            reason = str(e) if isinstance(e, ExtractionError) else f"{type(e).__name__}"
            await self.repo.set_status(doc, DocStatus.failed,
                                       review_notes=f"ingest failed: {reason}")
            await self.session.commit()
        return doc

    async def set_review(self, document_id: uuid.UUID, status: ReviewStatus,
                         reviewer: uuid.UUID | None = None, notes: str | None = None) -> Document:
        doc = await self._get(document_id)
        await self.repo.set_review(doc, status, reviewer, notes)
        await self.session.commit()
        return doc

    async def reindex(self, document_id: uuid.UUID) -> Document:
        doc = await self._get(document_id)
        doc.version += 1
        await self.repo.delete_chunks(doc.id)
        await self.session.flush()
        return await self.ingest(doc.id)
