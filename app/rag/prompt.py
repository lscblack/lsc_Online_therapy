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


def _clean(value, max_len: int) -> str:
    """Strip control chars/newlines, collapse whitespace, neutralise angle brackets, cap."""
    s = "".join(" " if (ch.isspace() or not ch.isprintable()) else ch for ch in str(value))
    s = s.replace("<", "").replace(">", "")
    return " ".join(s.split())[:max_len].strip()


def _esc(text: str) -> str:
    return str(text).replace("<", "&lt;").replace(">", "&gt;")


def build_system_prompt(profile, language: str | None) -> str:
    lang = normalize_language(language)
    parts = [t("persona", lang), t("language_directive", lang), t("scope", lang),
             t("grounding", lang), t("data_boundary", lang), t("referral", lang), t("abortion_legal", lang)]
    band = getattr(profile, "age_band", None)
    parts.append(t(_TONE.get(band, "tone_default"), lang))
    if profile is not None:
        for attr, key, cap in (("nickname", "address", 40), ("pronouns", "pronouns", 20),
                               ("tone_pref", "tone_pref", 40)):
            val = _clean(getattr(profile, attr, None) or "", cap)
            if val:
                parts.append(t(key, lang, **{attr: val}))
    return "\n\n".join(parts)


def _format_context(retrieval: RetrievalResult, lang: str) -> str:
    if not retrieval.chunks:
        return t("no_context", lang)
    blocks = []
    for i, c in enumerate(retrieval.chunks, 1):
        page = c.meta.get("page") if c.meta else None
        ref = f"{t('source_label', lang)}: {c.title}" + (f", p.{page}" if page else "")
        blocks.append(f'<source id="S{i}" ref="{_esc(ref)}" doc="{c.document_id}">\n'
                      f"{_esc(c.content)}\n</source>")
    return (t("context_header", lang) + "\n<context>\n" + "\n".join(blocks)
            + "\n</context>")


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
