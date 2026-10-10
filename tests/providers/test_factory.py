import pytest

from app.core.config import Settings
from app.providers import factory
from app.providers.embeddings_e5 import LocalE5Embeddings
from app.providers.fakes import FakeEmbeddings, FakeLLM, FakeSTT, FakeTTS
from app.providers.llm_openrouter import OpenRouterLLM
from app.providers.stt_openrouter import OpenRouterWhisperSTT
from app.providers.stubs_digitalumuganda import DigitalUmugandaSTT, DigitalUmugandaTTS
from app.providers.tts_openrouter import OpenRouterTTS


def _s(**kw):
    base = dict(
        database_url="postgresql+asyncpg://x/y_test",
        openrouter_api_key="k",
        llm_model="m/x",
    )
    base.update(kw)
    return Settings(_env_file=None, **base)


def test_fakes():
    s = _s(llm_provider="fake", embedding_provider="fake", stt_provider="fake", tts_provider="fake")
    assert isinstance(factory.get_llm(s), FakeLLM)
    assert isinstance(factory.get_embeddings(s), FakeEmbeddings)
    assert isinstance(factory.get_stt(s), FakeSTT)
    assert isinstance(factory.get_tts(s), FakeTTS)


def test_concrete_defaults():
    s = _s()
    assert isinstance(factory.get_llm(s), OpenRouterLLM)
    assert isinstance(factory.get_embeddings(s), LocalE5Embeddings)
    assert isinstance(factory.get_stt(s), OpenRouterWhisperSTT)
    assert isinstance(factory.get_tts(s), OpenRouterTTS)


def test_digitalumuganda():
    s = _s(stt_provider="digitalumuganda", tts_provider="digitalumuganda")
    assert isinstance(factory.get_stt(s), DigitalUmugandaSTT)
    assert isinstance(factory.get_tts(s), DigitalUmugandaTTS)


def test_missing_key_raises():
    with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
        factory.get_llm(_s(openrouter_api_key=""))
    with pytest.raises(ValueError, match="LLM_MODEL"):
        factory.get_llm(_s(llm_model=""))


def test_unknown_provider_raises():
    with pytest.raises(ValueError, match="Unknown"):
        factory.get_llm(_s(llm_provider="nope"))


async def test_fakes_behave():
    llm = FakeLLM(chunks=["a", "b"])
    assert [c async for c in llm.stream_chat([{"role": "user", "content": "x"}])] == ["a", "b"]
    e = FakeEmbeddings()
    v1 = await e.embed(["hello"], "query")
    v2 = await e.embed(["hello"], "query")
    assert v1 == v2 and len(v1[0]) == 768
    assert (await e.embed(["hello"], "passage")) == v1
    assert (await e.embed(["other"], "query")) != v1
    assert (await FakeSTT(text="hi").transcribe(b"x", None)).text == "hi"
    assert isinstance(await FakeTTS().synthesize("hi", "rw", None), bytes)
