import json

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.api.lang import accept_language
from app.core.db import get_session
from app.core.ratelimit import rate_limit
from app.models import User
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat import ChatService, ConversationNotFound

router = APIRouter(prefix="/v1/chat", tags=["chat"],
                   dependencies=[Depends(rate_limit("conversation", "rate_limit_chat_per_min", True))])


def _sse(event: str, data) -> str:
    payload = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    body = "\n".join(f"data: {line}" for line in payload.split("\n"))
    return f"event: {event}\n{body}\n\n"


@router.post("", response_model=ChatResponse)
async def chat(body: ChatRequest, user: User = Depends(current_user), hdr_lang: str | None = Depends(accept_language),
               session: AsyncSession = Depends(get_session)) -> ChatResponse:
    try:
        r = await ChatService(session).respond(user, body.message, body.conversation_id,
                                               body.language or hdr_lang)
    except ConversationNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found") from e
    return ChatResponse(answer=r.answer, citations=r.citations, conversation_id=r.conversation_id,
                        safety_flags=r.safety_flags, language=r.language)


@router.post("/stream")
async def chat_stream(body: ChatRequest, user: User = Depends(current_user),
                      hdr_lang: str | None = Depends(accept_language),
                      session: AsyncSession = Depends(get_session)) -> StreamingResponse:
    gen = ChatService(session).stream(user, body.message, body.conversation_id,
                                    body.language or hdr_lang)
    try:
        first = await gen.__anext__()  # run the pipeline now so errors become proper HTTP codes
    except ConversationNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found") from e

    async def events():
        yield _sse(first["event"], first["data"])
        async for ev in gen:
            yield _sse(ev["event"], ev["data"])

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache"})
