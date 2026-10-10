import json

import httpx
import pytest
import respx

from app.providers.llm_openrouter import OpenRouterLLM
from app.providers.stt_openrouter import OpenRouterWhisperSTT
from app.providers.stubs_digitalumuganda import DigitalUmugandaSTT, DigitalUmugandaTTS
from app.providers.tts_openrouter import OpenRouterTTS

BASE = "https://openrouter.ai/api/v1"


def _sse(*deltas):
    lines = [
        "data: " + json.dumps({"choices": [{"delta": {"content": d}}]}) + "\n\n" for d in deltas
    ]
    lines.insert(1, ": OPENROUTER PROCESSING\n\n")
    lines.append("data: " + json.dumps({"choices": [{"delta": {}}]}) + "\n\n")
    lines.append("data: [DONE]\n\n")
    return "".join(lines)


@respx.mock
async def test_llm_streams_chunks():
    route = respx.post(f"{BASE}/chat/completions").mock(
        return_value=httpx.Response(200, text=_sse("Hel", "lo", "!"))
    )
    llm = OpenRouterLLM(api_key="k", model="m/x", base_url=BASE)
    out = [c async for c in llm.stream_chat([{"role": "user", "content": "hi"}], temperature=0.1)]
    assert out == ["Hel", "lo", "!"]
    req = route.calls[0].request
    assert req.headers["authorization"] == "Bearer k"
    body = json.loads(req.content)
    assert body["stream"] is True and body["model"] == "m/x" and body["temperature"] == 0.1


@respx.mock
async def test_llm_http_error_raises():
    respx.post(f"{BASE}/chat/completions").mock(return_value=httpx.Response(401, text="no"))
    llm = OpenRouterLLM(api_key="k", model="m", base_url=BASE)
    with pytest.raises(httpx.HTTPStatusError):
        [c async for c in llm.stream_chat([])]


@respx.mock
async def test_stt_transcribes():
    route = respx.post(f"{BASE}/audio/transcriptions").mock(
        return_value=httpx.Response(200, json={"text": "muraho", "language": "rw"})
    )
    stt = OpenRouterWhisperSTT(api_key="k", model="openai/whisper-1", base_url=BASE)
    t = await stt.transcribe(b"audio", "rw")
    assert t.text == "muraho" and t.language == "rw"
    assert route.calls[0].request.headers["authorization"] == "Bearer k"


@respx.mock
async def test_tts_returns_bytes():
    route = respx.post(f"{BASE}/audio/speech").mock(
        return_value=httpx.Response(200, content=b"ID3mp3")
    )
    tts = OpenRouterTTS(api_key="k", model="openai/tts-1", base_url=BASE)
    assert await tts.synthesize("hello", "en", None) == b"ID3mp3"
    assert json.loads(route.calls[0].request.content)["input"] == "hello"


async def test_stubs_raise():
    with pytest.raises(NotImplementedError, match="planned"):
        await DigitalUmugandaSTT().transcribe(b"x", "rw")
    with pytest.raises(NotImplementedError, match="planned"):
        await DigitalUmugandaTTS().synthesize("x", "rw", None)
