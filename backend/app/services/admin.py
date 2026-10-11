import asyncio
import builtins
import time
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import User
from app.models.document import DocStatus, Document, ReviewStatus
from app.providers.base import EmbeddingProvider
from app.providers.factory import get_llm
from app.providers.registry import (
    ACTIVE_MODEL_KEY,
    ACTIVE_PROVIDER_KEY,
    PROVIDERS,
    list_models,
    provider_summaries,
)
from app.repositories.audit import AuditRepository
from app.repositories.documents import DocumentRepository
from app.repositories.settings import SettingsRepository
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
        self.settings_repo = SettingsRepository(session)

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

    # --- LLM provider/model management ---------------------------------------

    async def get_model_config(self) -> dict:
        """The active chat/voice provider+model (DB override, else the env default) plus the
        list of available providers and their curated models."""
        s = get_settings()
        prov = await self.settings_repo.get(ACTIVE_PROVIDER_KEY)
        model = await self.settings_repo.get(ACTIVE_MODEL_KEY)
        return {
            "active_provider": prov or s.default_llm_provider,
            "active_model": model or s.default_llm_model,
            "is_override": prov is not None,
            "providers": provider_summaries(s),
        }

    async def list_provider_models(self, provider: str) -> dict:
        """Live model ids for one provider (falls back to the curated list)."""
        if provider not in PROVIDERS:
            raise ValueError(f"Unknown provider: {provider}")
        return {"provider": provider, "models": await list_models(get_settings(), provider)}

    async def set_active_model(self, actor: User, provider: str, model: str) -> dict:
        provider, model = provider.strip(), model.strip()
        if provider not in PROVIDERS:
            raise ValueError(f"Unknown provider: {provider}")
        if not model:
            raise ValueError("model is required")
        await self.settings_repo.set(ACTIVE_PROVIDER_KEY, provider, updated_by=actor.id)
        await self.settings_repo.set(ACTIVE_MODEL_KEY, model, updated_by=actor.id)
        await self.audit.record(actor.id, "model.set", f"{provider}:{model}",
                                {"provider": provider, "model": model})
        await self.session.commit()
        return await self.get_model_config()

    async def test_model(self, provider: str, model: str, prompt: str) -> dict:
        """Probe a provider+model with a short prompt so the admin can compare before activating.
        Never raises: provider/credit/availability failures come back as ok=False + error."""
        provider, model = provider.strip(), model.strip()
        t0 = time.monotonic()
        try:
            llm = get_llm(model=model, provider=provider)
            messages = [{"role": "user", "content": prompt}]
            chunks = []
            async with asyncio.timeout(60):
                async for c in llm.stream_chat(messages, max_tokens=400):
                    chunks.append(c)
            text = "".join(chunks).strip()
            dt = int((time.monotonic() - t0) * 1000)
            if not text:
                return {"provider": provider, "model": model, "ok": False, "latency_ms": dt,
                        "sample": "", "error": "Model returned an empty response."}
            return {"provider": provider, "model": model, "ok": True, "latency_ms": dt,
                    "sample": text[:400], "error": None}
        except Exception as exc:  # noqa: BLE001 - a probe reports failure, never crashes the request
            dt = int((time.monotonic() - t0) * 1000)
            detail = getattr(getattr(exc, "response", None), "text", None) or str(exc)
            return {"provider": provider, "model": model, "ok": False, "latency_ms": dt,
                    "sample": "", "error": f"{type(exc).__name__}: {detail[:300]}"}
