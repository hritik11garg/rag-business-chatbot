from app.services.llm_service import generate_answer


def evaluate_confidence(question: str, answer: str, context: str) -> str:
    """
    Uses the same LLM to self-evaluate whether the answer is grounded in retrieved context.
    """

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

    result = generate_answer(
        question=evaluation_prompt,
        context=""
    )

    return result.strip().lower()
