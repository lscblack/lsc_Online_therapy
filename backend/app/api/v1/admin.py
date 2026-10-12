import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.core.db import get_session
from app.core.ratelimit import rate_limit
from app.models import User
from app.models.document import DocStatus, ReviewStatus
from app.schemas.admin import (
    AdminLoginRequest,
    AdminMeOut,
    AuditOut,
    DocumentOut,
    ModelConfigOut,
    ProviderModelsOut,
    ReviewIn,
    SetModelIn,
    TestModelIn,
    TestModelOut,
    UserOut,
)
from app.schemas.document import ChunkOut
from app.schemas.identity import TokenPair
from app.services.admin import AdminService
from app.services.identity import IdentityService, InvalidCredentials

router = APIRouter(prefix="/v1/admin", tags=["admin"])

MAX_PDF_BYTES = 20 * 1024 * 1024
_staff = require_role("admin", "reviewer")
_admin = require_role("admin")


def _404(what: str) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, f"{what} not found")


@router.post("/login", response_model=TokenPair,
             dependencies=[Depends(rate_limit("admin_login", "rate_limit_auth_per_min"))])
async def login(body: AdminLoginRequest,
                session: AsyncSession = Depends(get_session)) -> TokenPair:
    try:
        t = await IdentityService(session).login_admin(body.email, body.password)
    except InvalidCredentials as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials") from e
    return TokenPair(access_token=t.access_token, refresh_token=t.refresh_token)


@router.get("/me", response_model=AdminMeOut)
async def me(user: User = Depends(_staff)) -> AdminMeOut:
    """The authenticated staff user's role (from the DB row): the UI's single source of truth."""
    return AdminMeOut(role=user.role, email=user.email)


@router.post("/documents", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(title: str = Form(..., min_length=1, max_length=255),
                          file: UploadFile = File(...), language: str | None = Form(None),
                          topic_tags: str | None = Form(None),
                          user: User = Depends(_staff),
                          session: AsyncSession = Depends(get_session)):
    data = await file.read(MAX_PDF_BYTES + 1)
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Empty upload")
    if len(data) > MAX_PDF_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "File too large")
    tags = [t.strip() for t in (topic_tags or "").split(",") if t.strip()]
    return await AdminService(session).upload_document(
        user, title, file.filename, data, language, tags)


@router.get("/documents", response_model=list[DocumentOut])
async def list_documents(review_status: ReviewStatus | None = None,
                         doc_status: DocStatus | None = Query(None, alias="status"),
                         limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
                         user: User = Depends(_staff),
                         session: AsyncSession = Depends(get_session)):
    return await AdminService(session).list_documents(review_status, doc_status, limit, offset)


@router.get("/documents/{document_id}", response_model=DocumentOut)
async def get_document(document_id: uuid.UUID, user: User = Depends(_staff),
                       session: AsyncSession = Depends(get_session)):
    try:
        return await AdminService(session).get_document(document_id)
    except LookupError as e:
        raise _404("Document") from e


@router.get("/documents/{document_id}/chunks", response_model=list[ChunkOut])
async def document_chunks(document_id: uuid.UUID, user: User = Depends(_staff),
                          session: AsyncSession = Depends(get_session)):
    try:
        return await AdminService(session).get_document_chunks(document_id)
    except LookupError as e:
        raise _404("Document") from e


@router.post("/documents/{document_id}/review", response_model=DocumentOut)
async def review_document(document_id: uuid.UUID, body: ReviewIn,
                          user: User = Depends(_staff),
                          session: AsyncSession = Depends(get_session)):
    try:
        return await AdminService(session).review_document(
            user, document_id, body.status, body.notes)
    except LookupError as e:
        raise _404("Document") from e


@router.post("/documents/{document_id}/reindex", response_model=DocumentOut)
async def reindex_document(document_id: uuid.UUID, user: User = Depends(_staff),
                           session: AsyncSession = Depends(get_session)):
    try:
        return await AdminService(session).reindex_document(user, document_id)
    except LookupError as e:
        raise _404("Document") from e


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(document_id: uuid.UUID, user: User = Depends(_admin),
                          session: AsyncSession = Depends(get_session)) -> Response:
    try:
        await AdminService(session).delete_document(user, document_id)
    except LookupError as e:
        raise _404("Document") from e
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/users", response_model=list[UserOut])
async def list_users(limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
                     user: User = Depends(_admin),
                     session: AsyncSession = Depends(get_session)):
    return await AdminService(session).list_users(limit, offset)


@router.post("/users/{user_id}/disable", response_model=UserOut)
async def disable_user(user_id: uuid.UUID, user: User = Depends(_admin),
                       session: AsyncSession = Depends(get_session)):
    try:
        return await AdminService(session).disable_user(user, user_id)
    except LookupError as e:
        raise _404("User") from e


@router.get("/models", response_model=ModelConfigOut)
async def get_models(user: User = Depends(_admin),
                     session: AsyncSession = Depends(get_session)) -> ModelConfigOut:
    return ModelConfigOut(**await AdminService(session).get_model_config())


@router.get("/models/{provider}", response_model=ProviderModelsOut)
async def provider_models(provider: str, user: User = Depends(_admin),
                          session: AsyncSession = Depends(get_session)) -> ProviderModelsOut:
    try:
        return ProviderModelsOut(**await AdminService(session).list_provider_models(provider))
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e)) from e


@router.put("/models", response_model=ModelConfigOut)
async def set_model(body: SetModelIn, user: User = Depends(_admin),
                    session: AsyncSession = Depends(get_session)) -> ModelConfigOut:
    try:
        cfg = await AdminService(session).set_active_model(user, body.provider, body.model)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    return ModelConfigOut(**cfg)


@router.post("/models/test", response_model=TestModelOut)
async def test_model(body: TestModelIn, user: User = Depends(_admin),
                     session: AsyncSession = Depends(get_session)) -> TestModelOut:
    return TestModelOut(**await AdminService(session).test_model(body.provider, body.model, body.prompt))


@router.get("/audit", response_model=list[AuditOut])
async def list_audit(limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
                     user: User = Depends(_admin),
                     session: AsyncSession = Depends(get_session)):
    rows = await AdminService(session).list_audit(limit, offset)
    return [AuditOut.from_row(r) for r in rows]
