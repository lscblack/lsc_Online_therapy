"""Registry of OpenAI-compatible LLM providers the admin can switch between.

Each provider is a hosted (or local) endpoint. A provider is *enabled* only when its credential
is configured (or, for Ollama, when no key is needed). Models can be listed live per provider.
"""
import httpx

from app.core.config import Settings
from app.providers.openai_compat import OpenAICompatLLM

# name -> static definition
PROVIDERS: dict[str, dict] = {
    "ollama": {
        "label": "Ollama (local)", "base_url_attr": "ollama_base_url", "key_attr": None,
        "local": True, "tier": "local",
        "note": "Models running on your own machine — private, free, no rate limits.",
        "models": ["llama3:latest", "phi3:mini", "qwen2.5:1.5b"],
    },
    "requesty": {
        "label": "Requesty", "base_url": "https://router.requesty.ai/v1", "key_attr": "requesty_api_key",
        "tier": "free", "note": "Router with many free models; returns clean answers for reasoning models.",
        "models": ["google/gemma-4-31b-it", "openai/gpt-4o-mini", "deepseek/deepseek-chat"],
    },
    "openrouter": {
        "label": "OpenRouter", "base_url": "https://openrouter.ai/api/v1", "key_attr": "openrouter_api_key",
        "tier": "mixed", "note": "Large catalogue (free + paid). Some free models require enabling in privacy settings.",
        "models": ["inclusionai/ling-3.1-flash", "anthropic/claude-sonnet-5.5"],
        "extra_headers": {"HTTP-Referer": "https://ubuzima.rw", "X-Title": "Ubuzima"},
    },
    "cohere": {
        "label": "Cohere", "base_url": "https://api.cohere.ai/compatibility/v1", "key_attr": "cohere_api_key",
        "tier": "free", "note": "Command + Aya models. Aya Expanse is strong multilingual (good for Kinyarwanda).",
        "models": ["c4ai-aya-expanse-32b", "command-a-03-2025", "command-r-08-2024"],
    },
    "nvidia": {
        "label": "NVIDIA NIM", "base_url": "https://integrate.api.nvidia.com/v1", "key_attr": "nvidia_api_key",
        "tier": "free", "note": "NVIDIA-hosted open models.",
        "models": ["google/gemma-4-31b-it", "deepseek-ai/deepseek-v4.1-flash", "ibm/granite-3.0-8b-instruct"],
    },
    "aionlabs": {
        "label": "AionLabs", "base_url": "https://api.aionlabs.ai/v1", "key_attr": "aionlabs_api_key",
        "tier": "free", "note": "OpenAI-compatible AionLabs router.",
        "models": [],
    },
    "huggingface": {
        "label": "Hugging Face", "base_url": "https://router.huggingface.co/v1", "key_attr": "hf_api_key",
        "tier": "free", "note": "Hugging Face Inference Providers router (needs an HF token).",
        "models": ["meta-llama/Llama-3.3-70B-Instruct", "Qwen/Qwen2.5-72B-Instruct"],
    },
}

DEFAULT_PROVIDER = "ollama"
DEFAULT_MODEL = "llama3:latest"

# app_settings keys holding the admin-selected active LLM.
ACTIVE_PROVIDER_KEY = "active_provider"
ACTIVE_MODEL_KEY = "active_model"


def _base_url(settings: Settings, name: str) -> str:
    d = PROVIDERS[name]
    return d.get("base_url") or getattr(settings, d["base_url_attr"])


def _key(settings: Settings, name: str) -> str | None:
    attr = PROVIDERS[name].get("key_attr")
    return getattr(settings, attr) if attr else None


def is_enabled(settings: Settings, name: str) -> bool:
    d = PROVIDERS.get(name)
    if not d:
        return False
    if d.get("local"):
        return True
    return bool(_key(settings, name))


def provider_summaries(settings: Settings) -> list[dict]:
    out = []
    for name, d in PROVIDERS.items():
        out.append({
            "name": name, "label": d["label"], "tier": d["tier"], "note": d["note"],
            "enabled": is_enabled(settings, name), "local": bool(d.get("local")),
            "models": list(d.get("models", [])),
        })
    return out


def build_llm(settings: Settings, provider: str, model: str, *, max_tokens: int) -> OpenAICompatLLM:
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown provider: {provider!r}")
    return OpenAICompatLLM(
        _base_url(settings, provider), _key(settings, provider), model,
        max_tokens=max_tokens, extra_headers=PROVIDERS[provider].get("extra_headers"))


async def list_models(settings: Settings, provider: str) -> list[str]:
    """Live model ids for a provider (Ollama via /api/tags, others via /v1/models).
    Falls back to the curated list on any error."""
    d = PROVIDERS.get(provider)
    if not d:
        return []
    curated = list(d.get("models", []))
    if not is_enabled(settings, provider):
        return curated
    headers = {}
    key = _key(settings, provider)
    if key:
        headers["Authorization"] = f"Bearer {key}"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as client:
            if provider == "ollama":
                base = _base_url(settings, provider).rsplit("/v1", 1)[0]
                r = await client.get(f"{base}/api/tags")
                r.raise_for_status()
                names = [m["name"] for m in r.json().get("models", [])]
            else:
                r = await client.get(f"{_base_url(settings, provider).rstrip('/')}/models", headers=headers)
                r.raise_for_status()
                names = [m["id"] for m in r.json().get("data", [])]
        return sorted(set(names)) or curated
    except Exception:  # noqa: BLE001 - listing is best-effort; fall back to curated
        return curated
