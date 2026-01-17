from app.services.llm_service import generate_answer


def generate_faqs_from_chunk(chunk: str) -> list[dict]:
    """
    Uses the LLM to generate FAQ-style Q&A pairs from a document chunk.
    """

    prompt = f"""
    You are generating FAQs from business documentation.

    From the following text, generate 3 clear customer-facing FAQ question and answer pairs.

    Rules:
    - Questions must be realistic user questions
    - Answers must be directly based on the text
    - Keep them short and factual
    - Output STRICT JSON list format:

    [
    {{"question": "...", "answer": "..."}},
    {{"question": "...", "answer": "..."}}
    ]

    Text:
    {chunk}
    """

    response = generate_answer(question=prompt, context="")
    try:
        import json
        return json.loads(response)
    except Exception:
        return []
