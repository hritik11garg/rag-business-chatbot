from app.infrastructure.llm.openai_llm import OpenAILLMService


_llm = OpenAILLMService()


def generate_answer(*, question: str, context: str) -> str:
    """
    Backward-compatible wrapper.
    """
    return _llm.generate_answer(question=question, context=context)
