from app.domain.llm_service import LLMService
from app.infrastructure.llm.factory import build_llm_service

_llm: LLMService | None = None


def generate_answer(*, question: str, context: str) -> str:
    """
    Backward-compatible wrapper used by confidence scoring and FAQ
    generation. Builds the configured provider lazily on first use so
    importing this module never requires a valid API key.
    (Phase 2 will replace this with proper dependency injection.)
    """
    global _llm
    if _llm is None:
        _llm = build_llm_service()
    return _llm.generate_answer(question=question, context=context)
