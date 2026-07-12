import logging

from app.domain.llm_service import LLMService
from app.prompts import build_faq_generation_prompt, parse_faq_response

logger = logging.getLogger(__name__)


def generate_faqs_from_chunk(chunk: str, *, llm_service: LLMService) -> list[dict]:
    """
    Uses the LLM to generate FAQ-style Q&A pairs from a document chunk.
    """
    prompt = build_faq_generation_prompt(chunk=chunk)
    response = llm_service.generate_answer(question=prompt, context="")
    return parse_faq_response(response)


def generate_and_store_faqs(chunks, document_id, organization_id):
    """
    Background task to generate FAQs and store their embeddings
    without blocking upload requests.

    One failing chunk (rate limit, transient LLM error) must not sink
    the whole document — it is logged and skipped, and whatever FAQs
    the other chunks produced are still stored.
    """

    from app.composition.singletons import get_embedding_service, get_llm_service
    from app.db.session import SessionLocal
    from app.services.embedding_service import store_generated_faq_embeddings

    db = SessionLocal()
    try:
        llm_service = get_llm_service()

        all_faqs = []
        failed = 0
        for chunk in chunks:
            try:
                all_faqs.extend(
                    generate_faqs_from_chunk(chunk, llm_service=llm_service)
                )
            except Exception:
                failed += 1
                logger.warning(
                    "FAQ generation failed for a chunk; skipping",
                    exc_info=True,
                    extra={"document_id": document_id},
                )

        if all_faqs:
            store_generated_faq_embeddings(
                db,
                organization_id=organization_id,
                document_id=document_id,
                faqs=all_faqs,
                embedding_service=get_embedding_service(),
            )

        logger.info(
            "FAQ generation finished",
            extra={
                "document_id": document_id,
                "faqs_stored": len(all_faqs),
                "chunks_failed": failed,
                "chunks_total": len(chunks),
            },
        )
    finally:
        db.close()
