"""Safety policy: age-appropriate tone directives and user-facing escalation copy.
Source of truth for tone; rag.prompt.build_system_prompt calls tone_for()."""
from app.core.i18n import t
from app.models.profile import AgeBand

_TONE = {
    AgeBand.under15: "tone_under15",
    AgeBand.age_15_17: "tone_teen",
    AgeBand.age_18_19: "tone_teen",
    AgeBand.age_20_24: "tone_adult",
    AgeBand.age_25_plus: "tone_adult",
}

_CRISIS_COPY = {
    "crisis_self_harm": "crisis_self_harm",
    "gbv_sexual_violence": "crisis_gbv",
    "medical_emergency": "crisis_medical",
}


def tone_for(age_band: AgeBand | None, language: str | None = None) -> str:
    """Tone directive. Youngest band = simplest, most protective; unknown/undisclosed = default."""
    return t(_TONE.get(age_band, "tone_default"), language)


def crisis_message(category: str, language: str | None = None) -> str:
    """Empathetic, non-judgmental escalation text for a crisis category (no diagnosis)."""
    return t(_CRISIS_COPY.get(category, "crisis_self_harm"), language)


def out_of_scope_message(language: str | None = None) -> str:
    return t("out_of_scope", language)


def self_treatment_refusal(language: str | None = None) -> str:
    return t("self_treatment_refusal", language)


def eligibility_notice(language: str | None = None) -> str:
    return t("eligibility_notice", language)
