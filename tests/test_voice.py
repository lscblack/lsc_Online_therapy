import uuid

import pytest
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.core.db import get_engine, get_sessionmaker
from app.core.i18n import t
from app.models import Document, User
from app.models.conversation import Conversation
from app.providers.fakes import FakeLLM, FakeSTT
from app.services.voice import VoiceService
from tests.rag.test_retrieval import T_FP, _doc
from tests.test_identity import schema as _schema  # noqa: F401


@pytest.fixture(scope="module", autouse=True)
def schema(_schema):
    return _schema


@pytest.fixture(autouse=True)
async def _fresh_pool(schema):
    await get_engine().dispose()
    yield


@pytest.fixture(autouse=True)
def _fakes(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "embedding_provider", "fake")
    monkeypatch.setattr(s, "stt_provider", "fake")
    monkeypatch.setattr(s, "tts_provider", "fake")


@pytest.fixture
async def session():
    async with get_sessionmaker()() as s:
        await s.execute(delete(Document))
        await s.commit()
        yield s
        await s.rollback()
        await s.execute(delete(Document))
        await s.commit()


@pytest.fixture
async def user(session):
    u = User(anon_id=f"voice-{uuid.uuid4().hex}")
    session.add(u)
    await session.commit()
    return u


async def _headers(client):
    anon = (await client.post("/v1/identity/anon")).json()
    return {"Authorization": f"Bearer {anon['access_token']}"}


async def test_transcribe_returns_text(client):
    h = await _headers(client)
    r = await client.post("/v1/voice/transcribe", headers=h, data={"language": "en"},
                          files={"audio": ("clip.webm", b"\x00\x01audio", "audio/webm")})
    assert r.status_code == 200
    assert r.json() == {"text": "fake transcript", "language": "en"}
    assert (await client.post("/v1/voice/transcribe",
                              files={"audio": ("c.webm", b"x", "audio/webm")})).status_code == 401
    r = await client.post("/v1/voice/transcribe", headers=h,
                          files={"audio": ("c.webm", b"", "audio/webm")})
    assert r.status_code == 400


async def test_speak_returns_audio(client):
    h = await _headers(client)
    r = await client.post("/v1/voice/speak", headers=h,
                          json={"text": "Muraho", "language": "rw"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("audio/mpeg")
    assert r.content == b"FAKE-MP3:Muraho"
    assert (await client.post("/v1/voice/speak", json={"text": "x", "language": "en"})).status_code == 401
    assert (await client.post("/v1/voice/speak", headers=h,
                              json={"text": "  ", "language": "en"})).status_code == 422


async def test_voice_chat_roundtrip(session, user, monkeypatch):
    await _doc(session, "FP Guide", [T_FP])
    import app.services.voice as voice_mod
    monkeypatch.setattr(voice_mod, "get_stt", lambda: FakeSTT(text=T_FP, language="en"))
    llm = FakeLLM(["Condoms and pills are common methods [S1]."])
    res = await VoiceService(session, llm=llm).voice_chat(user, b"audio-bytes", filename="a.wav")
    assert res.transcript.text == T_FP
    assert res.chat.answer.startswith("Condoms") and res.chat.citations[0]["id"] == "S1"
    assert "[S1]" in res.chat.answer
    assert res.audio == b"FAKE-MP3:" + res.chat.answer.replace(" [S1]", "").encode()  # guarded, markers stripped
    conv = await session.get(Conversation, res.chat.conversation_id)
    assert conv.mode.value == "voice"


async def test_voice_chat_endpoint(client, session, monkeypatch):
    import base64

    import app.services.chat as chat_mod
    import app.services.voice as voice_mod
    await _doc(session, "FP Guide", [T_FP])
    monkeypatch.setattr(voice_mod, "get_stt", lambda: FakeSTT(text=T_FP, language="en"))
    monkeypatch.setattr(chat_mod, "get_llm", lambda: FakeLLM(["Condoms work well [S1]."]))
    h = await _headers(client)
    r = await client.post("/v1/voice/chat", headers=h, data={"language": "en"},
                          files={"audio": ("a.webm", b"zzz", "audio/webm")})
    assert r.status_code == 200
    j = r.json()
    assert j["transcript"] == T_FP and j["answer"].startswith("Condoms")
    assert j["citations"][0]["id"] == "S1" and j["conversation_id"] and "crisis" in j["safety_flags"]
    assert "[S1]" in j["answer"] and j["tts_available"] is True
    assert base64.b64decode(j["audio_base64"]) == b"FAKE-MP3:" + j["answer"].replace(" [S1]", "").encode()
    assert j["audio_mime"] == "audio/mpeg"
    r2 = await client.post("/v1/voice/chat", headers=h, data={"conversation_id": str(uuid.uuid4())},
                           files={"audio": ("a.webm", b"zzz", "audio/webm")})
    assert r2.status_code == 404
    monkeypatch.setattr(voice_mod, "get_stt", lambda: FakeSTT(text="   ", language="en"))
    r3 = await client.post("/v1/voice/chat", headers=h, files={"audio": ("a.webm", b"zzz", "audio/webm")})
    assert r3.status_code == 422


async def test_voice_chat_crisis_is_guarded(session, user, monkeypatch):
    import app.services.chat as chat_mod
    import app.services.voice as voice_mod

    async def boom(*a, **k):
        raise AssertionError("retrieval must not run for crisis")

    monkeypatch.setattr(chat_mod, "retrieve", boom)
    monkeypatch.setattr(voice_mod, "get_stt", lambda: FakeSTT(text="I want to kill myself", language="en"))
    llm = FakeLLM(["MODEL ANSWER MUST NOT APPEAR"])
    res = await VoiceService(session, llm=llm).voice_chat(user, b"audio", language="en")
    assert llm.calls == []
    assert "MODEL ANSWER" not in res.chat.answer
    assert t("crisis_self_harm", "en") in res.chat.answer
    assert res.chat.safety_flags["crisis"] is True
    assert b"MODEL ANSWER" not in res.audio and t("crisis_self_harm", "en").encode() in res.audio
    conv = await session.get(Conversation, res.chat.conversation_id)
    assert conv.mode.value == "voice"


async def test_tts_failure_still_returns_crisis_text(client, monkeypatch):
    import app.services.chat as chat_mod
    import app.services.voice as voice_mod
    monkeypatch.setattr(voice_mod, "get_stt", lambda: FakeSTT(text="I want to kill myself", language="en"))
    monkeypatch.setattr(chat_mod, "get_llm", lambda: FakeLLM(["MODEL ANSWER"]))
    h = await _headers(client)
    # Kinyarwanda hits the not-implemented Digital Umuganda TTS stub
    monkeypatch.setattr(get_settings(), "tts_provider", "digitalumuganda")
    r = await client.post("/v1/voice/chat", headers=h, data={"language": "en"},
                          files={"audio": ("a.webm", b"zzz", "audio/webm")})
    assert r.status_code == 200
    j = r.json()
    assert j["tts_available"] is False and j["audio_base64"] == ""
    assert t("crisis_self_harm", "en") in j["answer"] and "MODEL ANSWER" not in j["answer"]
    assert j["safety_flags"]["crisis"] is True


async def test_oversize_upload_413(client, monkeypatch):
    import app.api.v1.voice as voice_api
    monkeypatch.setattr(voice_api, "MAX_AUDIO_BYTES", 10)
    h = await _headers(client)
    r = await client.post("/v1/voice/chat", headers=h,
                          files={"audio": ("a.webm", b"x" * 50, "audio/webm")})
    assert r.status_code == 413


async def test_voice_chat_guarded_noncrisis_reaches_tts(session, user, monkeypatch):
    import app.services.voice as voice_mod
    await _doc(session, "FP Guide", [T_FP])
    monkeypatch.setattr(voice_mod, "get_stt",
                        lambda: FakeSTT(text="How do I deal with an unusual rash?", language="en"))
    llm = FakeLLM(["Sure, the answer is definitely 42 and you should do X."])
    res = await VoiceService(session, llm=llm).voice_chat(user, b"audio", language="en")
    assert "42" not in res.chat.answer and t("disclaimer", "en") in res.chat.answer
    assert t("referral_fallback", "en") in res.chat.answer
    assert b"42" not in res.audio and t("disclaimer", "en").encode() in res.audio
    assert res.tts_available is True


async def test_filename_derived_from_content_type():
    from starlette.datastructures import Headers
    from starlette.datastructures import UploadFile as UF

    from app.api.v1.voice import _filename
    f = UF(file=__import__("io").BytesIO(b"x"), filename=None,
           headers=Headers({"content-type": "audio/webm;codecs=opus"}))
    assert _filename(f) == "audio.webm"


async def test_accept_language_never_becomes_stt_hint(client, monkeypatch):
    import app.services.voice as voice_mod
    from app.providers.fakes import FakeTTS
    from app.services.chat import ChatService
    seen = {}

    class SpySTT:
        async def transcribe(self, audio, language, filename=None):
            seen["stt"] = language
            from app.providers.base import Transcript
            return Transcript(text="hello there", language=None)

    class SpyTTS(FakeTTS):
        async def synthesize(self, text, language, voice):
            seen["tts"] = language
            return await super().synthesize(text, language, voice)

    real = ChatService.respond

    async def spy_respond(self, user, message, cid, language=None, mode="text"):
        seen["reply"] = language
        return await real(self, user, message, cid, language, mode=mode)
    monkeypatch.setattr(ChatService, "respond", spy_respond)
    monkeypatch.setattr(voice_mod, "get_stt", lambda: SpySTT())
    monkeypatch.setattr(voice_mod, "get_tts", lambda: SpyTTS())
    h = await _headers(client)
    files = {"audio": ("a.webm", b"zzz", "audio/webm")}
    r = await client.post("/v1/voice/chat", headers={**h, "Accept-Language": "rw"}, files=files)
    assert r.status_code == 200, r.text
    assert seen["stt"] is None and seen["reply"] == "rw" and seen["tts"] == "rw"
    await client.post("/v1/voice/transcribe", headers={**h, "Accept-Language": "en-US"}, files=files)
    assert seen["stt"] is None
    await client.post("/v1/voice/transcribe", headers={**h, "Accept-Language": "en-US"},
                      files=files, data={"language": "rw"})
    assert seen["stt"] == "rw"
