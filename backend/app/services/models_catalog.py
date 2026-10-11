"""Curated catalogue of LLM models an admin can select from the dashboard.

These are OpenRouter model IDs. `recommended` are free models that were benchmarked on the
SRHR grounding task (EN + Kinyarwanda); `inclusionai/ling-3.1-flash` was the best free model
(grounded, bilingual, cites sources). Admins may also enter any other OpenRouter model ID
(e.g. a paid model such as `anthropic/claude-sonnet-5.5`) and test it before activating.
"""

LLM_SETTING_KEY = "llm_model"

# (id, label, tier, note)
CATALOG: list[dict] = [
    {"id": "inclusionai/ling-3.1-flash", "label": "Ling 3.1 Flash", "tier": "free",
     "note": "Best free model in our SRHR benchmark — grounded, bilingual (EN/RW), cites sources."},
    {"id": "openrouter/free", "label": "OpenRouter Auto (Free)", "tier": "free",
     "note": "Auto-routes to an available free model. Quality and availability vary."},
    {"id": "apodex/apodex-1.1-mini:free", "label": "Apodex 1.1 Mini", "tier": "free",
     "note": "Free and fast, but gave empty/weak answers in our benchmark."},
    {"id": "anthropic/claude-sonnet-5.5", "label": "Claude Sonnet 5.5", "tier": "paid",
     "note": "Highest quality; requires OpenRouter credits (paid)."},
    {"id": "google/gemini-2.5-flash", "label": "Gemini 2.5 Flash", "tier": "paid",
     "note": "Fast, strong multilingual; requires OpenRouter credits (paid)."},
]
