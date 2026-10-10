from types import SimpleNamespace

from app.rag.retrieval import RetrievalResult
from app.safety.guard import ensure_referral, ground
from app.safety.policy import tone_for
from app.models.profile import AgeBand


def _chunk():
    return SimpleNamespace(content="x", title="T", document_id="d", meta={})


GOOD = RetrievalResult(chunks=[_chunk(), _chunk()], max_score=0.9, in_knowledge=True)
BAD = RetrievalResult(chunks=[], max_score=0.1, in_knowledge=False)


def test_out_of_knowledge_answer_replaced_with_disclaimer_and_referral():
    r = ground("Take 3 tablets daily and you will be fine.", BAD, "en")
    assert not r.allowed and r.needs_referral and r.disclaimed
    assert "tablets" not in r.answer
    assert "doctor" in r.answer.lower() or "health" in r.answer.lower()


def test_out_of_knowledge_rw_disclaimer():
    r = ground("whatever", BAD, "rw")
    assert r.needs_referral and "muganga" in r.answer.lower()


def test_grounded_answer_passes():
    ans = "Condoms prevent pregnancy and STIs [S1]. Use one every time [S2]."
    r = ground(ans, GOOD, "en")
    assert r.allowed and r.answer == ans and not r.needs_referral and not r.disclaimed


def test_uncited_answer_gets_disclaimer_and_referral():
    r = ground("Condoms are great and always work.", GOOD, "en")
    assert not r.allowed and r.needs_referral and r.disclaimed
    assert "Condoms are great" in r.answer
    assert r.answer != "Condoms are great and always work."


def test_citation_to_nonexistent_source_is_unsupported():
    r = ground("Fact [S7].", GOOD, "en")
    assert not r.allowed and r.needs_referral


def test_dosage_instruction_blocked_even_when_cited():
    r = ground("Take 4 tablets of misoprostol under the tongue [S1].", GOOD, "en")
    assert not r.allowed and r.needs_referral
    assert "misoprostol" not in r.answer.lower()


def test_legal_determination_blocked():
    r = ground("You are legally allowed to have an abortion [S1].", GOOD, "en")
    assert not r.allowed and r.needs_referral
    assert "you are legally allowed" not in r.answer.lower()


def _ref(name, contact, verified=True):
    from datetime import datetime, timezone
    return SimpleNamespace(name=name, contact=contact, district=None,
                           verified_at=datetime.now(timezone.utc) if verified else None)


def test_ensure_referral_attaches_for_sensitive_category():
    out = ensure_referral("Here is some info.", "gbv_sexual_violence",
                          [_ref("Isange One Stop Centre", "0000")], "en")
    assert "Isange One Stop Centre" in out and out.startswith("Here is some info.")


def test_ensure_referral_unverified_contact_not_shown():
    out = ensure_referral("Info.", "abortion", [_ref("Clinic X", "PLACEHOLDER-123", False)], "en")
    assert "Clinic X" in out and "PLACEHOLDER-123" not in out


def test_ensure_referral_generic_fallback_when_catalog_empty():
    out = ensure_referral("Info.", "crisis_self_harm", [], "rw")
    assert len(out) > len("Info.") + 20


def test_ensure_referral_idempotent_and_skips_non_sensitive():
    r = [_ref("Clinic X", "111")]
    once = ensure_referral("Info.", "abortion", r, "en")
    assert ensure_referral(once, "abortion", r, "en") == once
    assert ensure_referral("Info.", "menstrual", r, "en") == "Info."


def test_tone_for_bands():
    young = tone_for(AgeBand.under15, "en")
    adult = tone_for(AgeBand.age_25_plus, "en")
    assert young != adult and "simple" in young.lower()
    assert tone_for(AgeBand.undisclosed, "en") == tone_for(None, "en")
    assert tone_for(AgeBand.under15, "rw") != young
