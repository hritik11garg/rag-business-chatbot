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


def generate_and_store_faqs(chunks, document_id, organization_id):
    """
    Background task to generate FAQs and store their embeddings
    without blocking upload requests.
    """

    from app.db.session import SessionLocal
    from app.services.embedding_service import store_generated_faq_embeddings

    db = SessionLocal()

    all_faqs = []
    for chunk in chunks:
        faqs = generate_faqs_from_chunk(chunk)
        all_faqs.extend(faqs)

    if all_faqs:
        store_generated_faq_embeddings(
            db,
            organization_id=organization_id,
            document_id=document_id,
            faqs=all_faqs,
        )

    db.close()
