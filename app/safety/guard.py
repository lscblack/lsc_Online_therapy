"""Grounding + output guard. Pure functions (no I/O)."""
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.core.i18n import normalize_language, t
from app.safety.policy import eligibility_notice, self_treatment_refusal
from app.safety.triage import SENSITIVE_CATEGORIES

if TYPE_CHECKING:  # type-only: avoid a runtime rag<->safety import cycle
    from app.rag.retrieval import RetrievalResult

_CITE = re.compile(r"\[S(\d+)\]")
_ABORTIFACIENT_CONTEXT = re.compile(
    r"misoprostol|mifepristone|cytotec|abortion|abortifacient|(end|terminate|induce)\w* (a |the |your |my )?pregnan|gukuramo inda")
_DOSAGE = re.compile(
    r"\b(take|use|insert|place|swallow|dissolve|put|drink)\b.{0,50}\b(\d+|one|two|three|four|five|six|eight|twelve)\b.{0,25}\b(pills?|tablets?|mcg|mg|capsules?)\b"
    r"|\b\d+\s?(mcg|mg|µg)\b|under the tongue|nywa ibinini|ibinini \d+|\d+ (bya )?ibinini|shyira ibinini")
_LEGAL_DETERMINATION = re.compile(
    r"\byou(?:'re| are| would be| will be) (?:not )?(?:legally |lawfully )?(?:allowed|eligible|entitled|permitted|qualified)\b"
    r"|\byou (?:can|may|cannot|can not|may not) legally\b|\byou qualify\b|urabyemerewe|ntabwo wemerewe|wemerewe n'itegeko")
SENSITIVE_STR = frozenset(c.value for c in SENSITIVE_CATEGORIES)


@dataclass(frozen=True)
class GuardResult:
    allowed: bool          # True only if the original answer may be sent unchanged
    answer: str            # answer to send (original, prefixed with disclaimer, or replaced)
    needs_referral: bool   # caller must run ensure_referral()
    disclaimed: bool       # a disclaimer/refusal was inserted
    reason: str = "ok"     # ok | out_of_knowledge | uncited | unsafe_dosage | legal_determination


def _n(text: str) -> str:
    return re.sub(r"[’‘`´]", "'", text.lower())


def ground(answer: str, retrieval: "RetrievalResult", language: str | None = None) -> GuardResult:
    lang = normalize_language(language)
    n = _n(answer)
    # Output-safety checks come first and apply even to cited answers.
    if _ABORTIFACIENT_CONTEXT.search(n) and _DOSAGE.search(n):
        return GuardResult(False, self_treatment_refusal(lang), True, True, "unsafe_dosage")
    if _LEGAL_DETERMINATION.search(n):
        return GuardResult(False, eligibility_notice(lang), True, True, "legal_determination")
    if not retrieval.in_knowledge or not retrieval.chunks:
        return GuardResult(False, t("disclaimer", lang), True, True, "out_of_knowledge")
    cited = [int(m) for m in _CITE.findall(answer)]
    if not cited or any(i < 1 or i > len(retrieval.chunks) for i in cited):
        return GuardResult(False, f"{t('disclaimer_prefix', lang)}\n\n{answer}", True, True, "uncited")
    return GuardResult(True, answer, False, False, "ok")


def _format_referral(r, lang: str) -> str:
    if getattr(r, "verified_at", None) is None:
        return f"- {r.name} ({t('referral_unverified', lang)})"
    where = f" ({r.district})" if getattr(r, "district", None) else ""
    return f"- {r.name}: {r.contact}{where}"


def ensure_referral(response: str, category: str, referrals: list, language: str | None = None,
                    force: bool = False) -> str:
    """Guarantee a referral/next step in the response for sensitive categories (or force=True,
    e.g. GuardResult.needs_referral). Idempotent. Unverified catalog entries are shown by name
    only (no contact details) until HDI verifies them."""
    if not force and str(category) not in SENSITIVE_STR:
        return response
    lang = normalize_language(language)
    if referrals:
        if all(r.name in response for r in referrals):
            return response
        block = t("referral_intro", lang) + "\n" + "\n".join(_format_referral(r, lang) for r in referrals)
    else:
        block = t("referral_fallback", lang)
        if block in response:
            return response
    return f"{response}\n\n{block}"
