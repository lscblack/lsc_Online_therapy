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
    r"misoprostol|mifepristone|cytotec|abortion|abortifacient|(end|terminate|induce)\w* (a |the |your |my )?pregnan"
    r"|gukuramo inda|kwikuramo inda|ukuremo inda|kuramo inda")
# Any quantity (digit, number word, indefinite) before a pill/tablet, or an imperative taking
# pills, in an abortifacient context is an instruction we never emit.
_DOSAGE = re.compile(
    r"\b(take|use|insert|place|swallow|dissolve|put|drink|chew|inject)\b.{0,60}\b(pills?|tablets?|capsules?|doses?)\b"
    r"|\b(\d+|[a-z]+)\s+(pills?|tablets?|capsules?)\b"
    r"|\b\d+\s?(mcg|mg|ug|µg)\b|under the tongue|\bdoses?\b"
    r"|nywa ibinini|shyira ibinini|ibinini \w+|\w+ bya misoprostol")
_ELIGIBILITY_CONTEXT = re.compile(r"abort|terminat|pregnan|gukuramo|kwikuramo|ukuremo|\binda\b")
_LEGAL_DETERMINATION = re.compile(
    r"\byou(?:'re| are| would be| will be) (?:not )?(?:legally |lawfully )?(?:allowed|eligible|entitled|permitted|qualified)\b"
    r"|\byou (?:can|may|cannot|can not|may not) legally\b|\byou qualify\b|urabyemerewe|ntabwo wemerewe|wemerewe n'itegeko")
_TREATMENT_FLAGS = frozenset({"self_treatment", "eligibility_question", "distress_cue"})
_CATALOG_SENSITIVE = frozenset({"crisis", "gbv", "emergency"})  # referral-catalog vocabulary
SENSITIVE_STR = frozenset(c.value for c in SENSITIVE_CATEGORIES) | _CATALOG_SENSITIVE


def _unpack(category) -> tuple[str, frozenset]:
    """Accept a Triage or a plain category string (triage OR catalog vocabulary)."""
    if hasattr(category, "category") and hasattr(category, "flags"):
        return str(category.category), frozenset(category.flags) | (
            _CATALOG_SENSITIVE if category.is_crisis else frozenset())
    return str(category or ""), frozenset()


def is_sensitive(category, flags=()) -> bool:
    cat, f = _unpack(category)
    return cat in SENSITIVE_STR or bool((f | frozenset(flags)) & (_TREATMENT_FLAGS | _CATALOG_SENSITIVE))


@dataclass(frozen=True)
class GuardResult:
    allowed: bool          # True only if the original answer may be sent unchanged
    answer: str            # answer to send (original, prefixed with disclaimer, or replaced)
    needs_referral: bool   # caller must run ensure_referral()
    disclaimed: bool       # a disclaimer/refusal was inserted
    reason: str = "ok"     # ok | out_of_knowledge | uncited | unsafe_dosage | legal_determination


def _n(text: str) -> str:
    return re.sub(r"[’‘`´]", "'", text.lower())


def is_hard_unsafe(text: str) -> bool:
    """True if the text contains an output that must be REPLACED, never shown (self-treatment
    dosage for an abortifacient, or a legal-eligibility determination). Used to gate live
    streaming so unsafe content is never sent to the client."""
    n = _n(text)
    return bool((_ABORTIFACIENT_CONTEXT.search(n) and _DOSAGE.search(n))
                or (_ELIGIBILITY_CONTEXT.search(n) and _LEGAL_DETERMINATION.search(n)))


def ground(answer: str, retrieval: "RetrievalResult", language: str | None = None,
           category=None) -> GuardResult:
    """`category` (optional; Triage or string) marks the turn sensitive: ungrounded answers are
    then REPLACED by the disclaimer rather than prefixed."""
    lang = normalize_language(language)
    n = _n(answer)
    # Output-safety checks come first and apply even to cited answers.
    if _ABORTIFACIENT_CONTEXT.search(n) and _DOSAGE.search(n):
        return GuardResult(False, self_treatment_refusal(lang), True, True, "unsafe_dosage")
    if _ELIGIBILITY_CONTEXT.search(n) and _LEGAL_DETERMINATION.search(n):
        return GuardResult(False, eligibility_notice(lang), True, True, "legal_determination")
    if not retrieval.in_knowledge or not retrieval.chunks:
        return GuardResult(False, t("disclaimer", lang), True, True, "out_of_knowledge")
    cited = [int(m) for m in _CITE.findall(answer)]
    if not cited or any(i < 1 or i > len(retrieval.chunks) for i in cited):
        if is_sensitive(category):
            return GuardResult(False, t("disclaimer", lang), True, True, "uncited")
        return GuardResult(False, f"{t('disclaimer_prefix', lang)}\n\n{answer}", True, True, "uncited")
    return GuardResult(True, answer, False, False, "ok")


def _format_referral(r, lang: str) -> str:
    if getattr(r, "verified_at", None) is None:
        return f"- {r.name} ({t('referral_unverified', lang)})"
    where = f" ({r.district})" if getattr(r, "district", None) else ""
    return f"- {r.name}: {r.contact}{where}"


def ensure_referral(response: str, category, referrals: list, language: str | None = None,
                    force: bool = False, flags=()) -> str:
    """Guarantee an actionable next step for sensitive turns. Signature:
    ensure_referral(response, category: Triage | str, referrals, language=None, force=False, flags=()).
    `category` may be a Triage (flags + crisis honoured automatically) or a string in EITHER the
    triage vocabulary (crisis_self_harm, abortion, ...) or the catalog vocabulary
    (crisis/gbv/emergency). Self-treatment / eligibility / distress flags also trigger it.
    Idempotent. Unverified entries are listed by name only (no contact), and unless at least one
    VERIFIED referral is present the generic fallback next step is appended as well."""
    if not (force or is_sensitive(category, flags)):
        return response
    lang = normalize_language(language)
    fallback = t("referral_fallback", lang)
    has_verified = any(getattr(r, "verified_at", None) is not None for r in referrals)
    parts = []
    if referrals and not all(r.name in response for r in referrals):
        parts.append(t("referral_intro", lang) + "\n"
                     + "\n".join(_format_referral(r, lang) for r in referrals))
    if not has_verified and fallback not in response:
        parts.append(fallback)
    return response if not parts else response + "\n\n" + "\n\n".join(parts)
