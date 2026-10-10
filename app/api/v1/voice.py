import base64
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.core.db import get_session
from app.models import User
from app.schemas.voice import SpeakRequest, TranscribeResponse, VoiceChatResponse
from app.services.chat import ConversationNotFound
from app.services.voice import EmptyTranscript, VoiceService

router = APIRouter(prefix="/v1/voice", tags=["voice"])
MAX_AUDIO_BYTES = 10 * 1024 * 1024


async def _read_audio(file: UploadFile) -> bytes:
    data = await file.read(MAX_AUDIO_BYTES + 1)
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Empty audio upload")
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Audio too large")
    return data


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe(audio: UploadFile = File(...), language: str | None = Form(None),
                     user: User = Depends(current_user),
                     session: AsyncSession = Depends(get_session)) -> TranscribeResponse:
    data = await _read_audio(audio)
    tr = await VoiceService(session).transcribe(data, language, audio.filename)
    return TranscribeResponse(text=tr.text, language=tr.language)


@router.post("/speak")
async def speak(body: SpeakRequest, user: User = Depends(current_user),
                session: AsyncSession = Depends(get_session)) -> Response:
    audio = await VoiceService(session).speak(body.text, body.language, body.voice)
    return Response(content=audio, media_type="audio/mpeg")


@router.post("/chat", response_model=VoiceChatResponse)
async def voice_chat(audio: UploadFile = File(...), language: str | None = Form(None),
                     voice: str | None = Form(None), conversation_id: uuid.UUID | None = Form(None),
                     user: User = Depends(current_user),
                     session: AsyncSession = Depends(get_session)) -> VoiceChatResponse:
    data = await _read_audio(audio)
    try:
        r = await VoiceService(session).voice_chat(user, data, language, voice, conversation_id,
                                                   audio.filename)
    except ConversationNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found") from e
    except EmptyTranscript as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "No speech recognised") from e
    c = r.chat
    return VoiceChatResponse(
        transcript=r.transcript.text, answer=c.answer, citations=c.citations,
        conversation_id=c.conversation_id, safety_flags=c.safety_flags, language=c.language,
        audio_base64=base64.b64encode(r.audio).decode(), audio_mime=r.audio_mime)
