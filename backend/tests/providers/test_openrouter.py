import json

import httpx
import pytest
import respx

from app.providers.base import ProviderError
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


def _chunked(text, n=7):
    async def gen():
        for i in range(0, len(text), n):
            yield text[i : i + n].encode()

    return gen()


@respx.mock
async def test_llm_chunk_boundaries_and_done_stops():
    body = _sse("Hel", "lo") + "data: " + json.dumps({"choices": [{"delta": {"content": "X"}}]}) + "\n\n"
    respx.post(f"{BASE}/chat/completions").mock(
        return_value=httpx.Response(200, content=_chunked(body))
    )
    llm = OpenRouterLLM(api_key="k", model="m", base_url=BASE)
    assert [c async for c in llm.stream_chat([])] == ["Hel", "lo"]


@respx.mock
async def test_llm_midstream_error_raises():
    body = (
        "data: " + json.dumps({"choices": [{"delta": {"content": "Hi"}}]}) + "\n\n"
        + "data: " + json.dumps({"error": {"code": 502, "message": "upstream"}}) + "\n\n"
    )
    respx.post(f"{BASE}/chat/completions").mock(
        return_value=httpx.Response(200, content=_chunked(body))
    )
    llm = OpenRouterLLM(api_key="k", model="m", base_url=BASE)
    got = []
    with pytest.raises(ProviderError, match="upstream"):
        async for c in llm.stream_chat([]):
            got.append(c)
    assert got == ["Hi"]


@respx.mock
async def test_llm_malformed_json_raises():
    respx.post(f"{BASE}/chat/completions").mock(
        return_value=httpx.Response(200, text="data: {not json\n\n")
    )
    llm = OpenRouterLLM(api_key="k", model="m", base_url=BASE)
    with pytest.raises(ProviderError):
        [c async for c in llm.stream_chat([])]


def test_constructors_validate():
    with pytest.raises(ValueError):
        OpenRouterLLM(api_key="", model="m")
    with pytest.raises(ValueError):
        OpenRouterLLM(api_key="k", model="")
    with pytest.raises(ValueError):
        OpenRouterWhisperSTT(api_key="", model="m")
    with pytest.raises(ValueError):
        OpenRouterTTS(api_key="k", model="")


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
    req = route.calls[0].request
    assert req.headers["content-type"].startswith("multipart/form-data")
    body = req.content
    assert b'name="model"' in body and b"openai/whisper-1" in body
    assert b'name="language"' in body and b"rw" in body
    assert b'filename="audio.webm"' in body and b"Content-Type: audio/webm" in body


@respx.mock
async def test_stt_filename_sets_mime():
    route = respx.post(f"{BASE}/audio/transcriptions").mock(
        return_value=httpx.Response(200, json={"text": "x"})
    )
    stt = OpenRouterWhisperSTT(api_key="k", model="m", base_url=BASE)
    t = await stt.transcribe(b"a", None, filename="clip.wav")
    assert t.text == "x"
    body = route.calls[0].request.content
    assert b'filename="clip.wav"' in body and b"audio/wav" in body and b'name="language"' not in body
    assert route.calls[0].request.headers["authorization"] == "Bearer k"


@respx.mock
async def test_tts_returns_bytes():
    route = respx.post(f"{BASE}/audio/speech").mock(
        return_value=httpx.Response(200, content=b"ID3mp3")
    )
    tts = OpenRouterTTS(api_key="k", model="openai/tts-1", base_url=BASE)
    assert await tts.synthesize("hello", "en", None) == b"ID3mp3"
    body = json.loads(route.calls[0].request.content)
    assert body["input"] == "hello" and body["voice"] == "alloy"
    assert body["response_format"] == "mp3" and body["model"] == "openai/tts-1"
    await tts.synthesize("hi", "en", "nova")
    assert json.loads(route.calls[1].request.content)["voice"] == "nova"


async def test_stubs_raise():
    with pytest.raises(NotImplementedError, match="planned"):
        await DigitalUmugandaSTT().transcribe(b"x", "rw")
    with pytest.raises(NotImplementedError, match="planned"):
        await DigitalUmugandaTTS().synthesize("x", "rw", None)
