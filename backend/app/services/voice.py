"""Turn-based voice: STT -> the SAME safe ChatService pipeline -> TTS of the GUARDED answer.

Safety: voice_chat() never generates text itself. The text that is spoken is exactly
ChatResult.answer from ChatService.respond() (triage, crisis bypass, grounding guard, referrals
already applied), so every Task 8/9 guarantee holds for voice.
"""
import logging
import re
import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.i18n import normalize_language
from app.models import User
from app.providers.base import Transcript
from app.providers.factory import get_stt, get_tts
from app.services.chat import ChatResult, ChatService


logger = logging.getLogger(__name__)
_CITE = re.compile(r"\s*\[S\d+\]")


def strip_citations(text: str) -> str:
    """Remove [S#] citation markers for speech (the written answer keeps them)."""
    return _CITE.sub("", text).strip()


class EmptyTranscript(ValueError):
    """Speech-to-text produced no usable text."""


@dataclass
class VoiceChatResult:
    transcript: Transcript
    chat: ChatResult
    audio: bytes
    audio_mime: str = "audio/mpeg"
    tts_available: bool = True


class VoiceService:
    def __init__(self, session: AsyncSession, llm=None) -> None:
        self.session = session
        self.chat = ChatService(session, llm=llm)

    async def transcribe(self, audio: bytes, language: str | None = None,
                         filename: str | None = None) -> Transcript:
        return await get_stt().transcribe(audio, language, filename)

    async def speak(self, text: str, language: str, voice: str | None = None) -> bytes:
        return await get_tts().synthesize(text, normalize_language(language), voice)

    async def voice_chat(self, user: User, audio: bytes, language: str | None = None,
                         voice: str | None = None, conversation_id: uuid.UUID | None = None,
                         filename: str | None = None,
                         reply_language: str | None = None) -> VoiceChatResult:
        # `language` is the explicit STT hint only; reply_language (e.g. Accept-Language) never is.
        transcript = await self.transcribe(audio, language, filename)
        if not transcript.text or not transcript.text.strip():
            raise EmptyTranscript("no speech recognised")
        result = await self.chat.respond(user, transcript.text, conversation_id,
                                         language or reply_language or transcript.language, mode="voice")
        # Citation markers are stripped for speech only; result.answer keeps them.
        spoken = strip_citations(result.answer)
        try:
            speech = await self.speak(spoken, result.language, voice)
        except Exception as exc:  # noqa: BLE001 - the guarded text must reach the client regardless
            logger.error("TTS failed (%s); returning text-only voice reply", type(exc).__name__)
            return VoiceChatResult(transcript, result, b"", tts_available=False)
        return VoiceChatResult(transcript, result, speech)
