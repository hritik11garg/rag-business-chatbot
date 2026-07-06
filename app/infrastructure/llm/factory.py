from dataclasses import dataclass

from app.core.config import settings
from app.domain.llm_service import LLMService
from app.infrastructure.llm.anthropic_llm import AnthropicLLMService
from app.infrastructure.llm.openai_compatible import OpenAICompatibleLLMService


@dataclass(frozen=True)
class ProviderDefaults:
    base_url: str | None
    model: str
    api_key_setting: str  # name of the Settings field holding the key


# Every provider here speaks the OpenAI chat-completions protocol,
# so they all share one adapter and differ only in these defaults.
_OPENAI_COMPATIBLE: dict[str, ProviderDefaults] = {
    "openai": ProviderDefaults(
        base_url=None,  # SDK default: https://api.openai.com/v1
        model="gpt-4o-mini",
        api_key_setting="OPENAI_API_KEY",
    ),
    "groq": ProviderDefaults(
        base_url="https://api.groq.com/openai/v1",
        model="llama-3.3-70b-versatile",
        api_key_setting="GROQ_API_KEY",
    ),
    "gemini": ProviderDefaults(
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        model="gemini-2.5-flash",
        api_key_setting="GEMINI_API_KEY",
    ),
    "ollama": ProviderDefaults(
        base_url="http://localhost:11434/v1",
        model="llama3.2",
        api_key_setting="",  # local server — no key
    ),
}

_ANTHROPIC_DEFAULT_MODEL = "claude-haiku-4-5-20251001"


def build_llm_service() -> LLMService:
    """
    Build the LLM adapter selected by LLM_PROVIDER in .env.
    LLM_MODEL / LLM_BASE_URL / LLM_TEMPERATURE override the defaults.
    """
    provider = settings.LLM_PROVIDER.lower()

    if provider == "anthropic":
        if not settings.ANTHROPIC_API_KEY:
            raise RuntimeError(
                "LLM_PROVIDER=anthropic but ANTHROPIC_API_KEY is not set in .env"
            )
        return AnthropicLLMService(
            api_key=settings.ANTHROPIC_API_KEY,
            model=settings.LLM_MODEL or _ANTHROPIC_DEFAULT_MODEL,
            temperature=settings.LLM_TEMPERATURE,
        )

    defaults = _OPENAI_COMPATIBLE.get(provider)
    if defaults is None:
        valid = ", ".join([*_OPENAI_COMPATIBLE, "anthropic"])
        raise RuntimeError(
            f"Unknown LLM_PROVIDER '{settings.LLM_PROVIDER}'. Valid options: {valid}"
        )

    if provider == "ollama":
        api_key = "ollama"  # the SDK requires a non-empty key; Ollama ignores it
    else:
        api_key = getattr(settings, defaults.api_key_setting)
        if not api_key:
            raise RuntimeError(
                f"LLM_PROVIDER={provider} but {defaults.api_key_setting} "
                "is not set in .env"
            )

    return OpenAICompatibleLLMService(
        api_key=api_key,
        base_url=settings.LLM_BASE_URL or defaults.base_url,
        model=settings.LLM_MODEL or defaults.model,
        temperature=settings.LLM_TEMPERATURE,
    )
