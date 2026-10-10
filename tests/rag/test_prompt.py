import uuid

from app.models.profile import AgeBand, Profile
from app.rag.prompt import assemble, build_system_prompt
from app.rag.retrieval import RetrievalResult, RetrievedChunk


def _result():
    doc = uuid.uuid4()
    chunks = [RetrievedChunk(content="Condoms prevent STIs.", document_id=doc, title="FP Guide",
                             score=0.8, meta={"page": 3}, chunk_id=uuid.uuid4())]
    return RetrievalResult(chunks=chunks, max_score=0.8, in_knowledge=True), doc


def test_prompt_includes_persona_scope_and_citations():
    sp = build_system_prompt(None, "en").lower()
    for word in ["non-judgmental", "only", "context", "cite", "doctor", "abortion",
                 "not a diagnosis", "rwanda"]:
        assert word in sp, word
    res, doc = _result()
    hist = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]
    msgs = assemble("Do condoms work?", res, hist, None, "en")
    assert msgs[0]["role"] == "system"
    assert msgs[1:3] == hist
    last = msgs[-1]
    assert last["role"] == "user"
    assert "Condoms prevent STIs." in last["content"] and "[S1]" in last["content"]
    assert "FP Guide" in last["content"] and "Do condoms work?" in last["content"]
    assert all(set(m) == {"role", "content"} for m in msgs)


def test_assemble_out_of_knowledge_states_no_context():
    res = RetrievalResult(chunks=[], max_score=0.0, in_knowledge=False)
    last = assemble("q?", res, [], None, "en")[-1]["content"]
    assert "no relevant" in last.lower() and "q?" in last


def test_prompt_respects_age_band_and_language():
    young = build_system_prompt(Profile(age_band=AgeBand.under15), "en")
    older = build_system_prompt(Profile(age_band=AgeBand.age_20_24), "en")
    assert young != older
    assert "very simple" in young.lower()
    rw = build_system_prompt(None, "rw")
    en = build_system_prompt(None, "en")
    assert rw != en and "Kinyarwanda" in rw
    p = build_system_prompt(Profile(nickname="Keza", pronouns="she/her",
                                    age_band=AgeBand.age_18_19), "en")
    assert "Keza" in p and "she/her" in p
    assert "Keza" not in build_system_prompt(Profile(age_band=AgeBand.age_18_19), "en")
    # unknown language defaults safely
    assert build_system_prompt(None, "zz") == en
