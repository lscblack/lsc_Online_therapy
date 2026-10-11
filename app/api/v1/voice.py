import base64
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user
from app.api.lang import accept_language
from app.core.db import get_session
from app.core.ratelimit import rate_limit
from app.models import User
from app.schemas.voice import SpeakRequest, TranscribeResponse, VoiceChatResponse
from app.services.chat import ConversationNotFound
from app.services.voice import EmptyTranscript, VoiceService

router = APIRouter(prefix="/v1/voice", tags=["voice"],
                   dependencies=[Depends(rate_limit("voice", "rate_limit_chat_per_min", True))])
MAX_AUDIO_BYTES = 10 * 1024 * 1024
# STT only uses the filename extension to infer format; if the upload has no filename we derive
# one from its content-type.
_EXT = {"audio/webm": "webm", "audio/ogg": "ogg", "audio/mpeg": "mp3", "audio/mp3": "mp3",
        "audio/wav": "wav", "audio/x-wav": "wav", "audio/wave": "wav", "audio/mp4": "m4a",
        "audio/x-m4a": "m4a", "audio/flac": "flac"}


def _filename(file: UploadFile) -> str | None:
    if file.filename:
        return file.filename
    base = (file.content_type or "").split(";")[0].strip().lower()
    return f"audio.{_EXT[base]}" if base in _EXT else None


async def _read_audio(file: UploadFile) -> bytes:
    data = await file.read(MAX_AUDIO_BYTES + 1)
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Empty audio upload")
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Audio too large")
    return data


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe(audio: UploadFile = File(...), language: str | None = Form(None),
                     user: User = Depends(current_user), hdr_lang: str | None = Depends(accept_language),
                     session: AsyncSession = Depends(get_session)) -> TranscribeResponse:
    data = await _read_audio(audio)
    tr = await VoiceService(session).transcribe(data, language or hdr_lang, _filename(audio))
    return TranscribeResponse(text=tr.text, language=tr.language)


@router.post("/speak")
async def speak(body: SpeakRequest, user: User = Depends(current_user), hdr_lang: str | None = Depends(accept_language),
                session: AsyncSession = Depends(get_session)) -> Response:
    audio = await VoiceService(session).speak(body.text,
                                         body.language if "language" in body.model_fields_set
                                         else (hdr_lang or body.language), body.voice)
    return Response(content=audio, media_type="audio/mpeg")


@router.post("/chat", response_model=VoiceChatResponse)
async def voice_chat(audio: UploadFile = File(...), language: str | None = Form(None),
                     voice: str | None = Form(None), conversation_id: uuid.UUID | None = Form(None),
                     user: User = Depends(current_user), hdr_lang: str | None = Depends(accept_language),
                     session: AsyncSession = Depends(get_session)) -> VoiceChatResponse:
    data = await _read_audio(audio)
    try:
        r = await VoiceService(session).voice_chat(user, data, language or hdr_lang, voice, conversation_id,
                                                   _filename(audio))
    except ConversationNotFound as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found") from e
    except EmptyTranscript as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "No speech recognised") from e
    c = r.chat
    return VoiceChatResponse(
        transcript=r.transcript.text, answer=c.answer, citations=c.citations,
        conversation_id=c.conversation_id, safety_flags=c.safety_flags, language=c.language,
        audio_base64=base64.b64encode(r.audio).decode(), audio_mime=r.audio_mime,
        tts_available=r.tts_available)
