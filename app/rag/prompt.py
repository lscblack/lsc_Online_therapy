"""System prompt + OpenAI-style message assembly. Pure functions, no I/O."""
from app.core.i18n import normalize_language, t
from app.models.profile import AgeBand
from app.rag.retrieval import RetrievalResult

_TONE = {
    AgeBand.under15: "tone_under15",
    AgeBand.age_15_17: "tone_teen",
    AgeBand.age_18_19: "tone_teen",
    AgeBand.age_20_24: "tone_adult",
    AgeBand.age_25_plus: "tone_adult",
}


def build_system_prompt(profile, language: str | None) -> str:
    lang = normalize_language(language)
    parts = [t("persona", lang), t("language_directive", lang), t("scope", lang),
             t("grounding", lang), t("referral", lang), t("abortion_legal", lang)]
    band = getattr(profile, "age_band", None)
    parts.append(t(_TONE.get(band, "tone_default"), lang))
    if profile is not None:
        if getattr(profile, "nickname", None):
            parts.append(t("address", lang, nickname=profile.nickname))
        if getattr(profile, "pronouns", None):
            parts.append(t("pronouns", lang, pronouns=profile.pronouns))
        if getattr(profile, "tone_pref", None):
            parts.append(t("tone_pref", lang, tone_pref=profile.tone_pref))
    return "\n\n".join(parts)


def _format_context(retrieval: RetrievalResult, lang: str) -> str:
    if not retrieval.chunks:
        return t("no_context", lang)
    blocks = []
    for i, c in enumerate(retrieval.chunks, 1):
        page = c.meta.get("page") if c.meta else None
        ref = f"{t('source_label', lang)}: {c.title}" + (f", p.{page}" if page else "")
        blocks.append(f"[S{i}] ({ref}; doc={c.document_id})\n{c.content}")
    return t("context_header", lang) + "\n\n" + "\n\n".join(blocks)


def assemble(query: str, retrieval: RetrievalResult, history: list[dict], profile,
             language: str | None) -> list[dict]:
    """Returns [system, *history, user]; each a {"role","content"} dict. The final user
    turn holds the numbered context ([S1]..[Sn], in retrieval order) then the question.
    If retrieval is out of knowledge (below threshold) the context is replaced by a
    no-context instruction so the model refers the user to a professional."""
    lang = normalize_language(language)
    ctx = _format_context(retrieval, lang) if retrieval.in_knowledge else t("no_context", lang)
    user = f"{ctx}\n\n{t('question_header', lang)} {query}"
    prior = [{"role": m["role"], "content": m["content"]} for m in history]
    return [{"role": "system", "content": build_system_prompt(profile, lang)},
            *prior, {"role": "user", "content": user}]
