import pytest

from app.providers.embeddings_e5 import LocalE5Embeddings


def test_prefix_applied_without_model():
    assert LocalE5Embeddings.prefixed(["a"], "query") == ["query: a"]
    assert LocalE5Embeddings.prefixed(["a"], "passage") == ["passage: a"]


@pytest.mark.integration
async def test_embed_dim_768():
    e = LocalE5Embeddings("intfloat/multilingual-e5-base")
    seen = []
    orig = e._encode

    def spy(texts):
        seen.extend(texts)
        return orig(texts)

    e._encode = spy
    vecs = await e.embed(["Muraho", "hello"], "passage")
    assert len(vecs) == 2 and all(len(v) == 768 for v in vecs)
    assert seen == ["passage: Muraho", "passage: hello"]
