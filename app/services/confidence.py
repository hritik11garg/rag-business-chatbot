from app.domain.llm_service import LLMService


class ConfidenceEvaluator:
    """
    Uses the LLM to self-evaluate whether an answer is grounded in the
    retrieved context. The LLM is injected so callers control which
    provider (or fake, in tests) is used.
    """

    def __init__(self, *, llm_service: LLMService):
        self.llm_service = llm_service

    def evaluate(self, *, question: str, answer: str, context: str) -> str:
        evaluation_prompt = f"""
    You are a strict evaluator for a retrieval-augmented chatbot.

    Question: {question}
    Answer: {answer}

    Context used:
    {context}

    Rate the grounding quality:

    HIGH = directly supported in context
    MEDIUM = partially supported / inferred
    LOW = not supported or weak

    Return ONLY one word: HIGH, MEDIUM, or LOW.
    """

        result = self.llm_service.generate_answer(
            question=evaluation_prompt,
            context="",
        )

        return result.strip().lower()
