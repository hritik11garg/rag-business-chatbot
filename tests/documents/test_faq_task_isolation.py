"""FAQ background task: one failing chunk must not sink the document."""

import app.services.faq_generator as faq_module


def test_failed_chunk_is_skipped_and_rest_are_stored(monkeypatch):
    def flaky_generate(chunk, *, llm_service):
        if chunk == "bad":
            raise RuntimeError("rate limited")
        return [{"question": f"q-{chunk}", "answer": f"a-{chunk}"}]

    stored = {}

    def fake_store(db, *, organization_id, document_id, faqs, embedding_service):
        stored["faqs"] = faqs

    monkeypatch.setattr(faq_module, "generate_faqs_from_chunk", flaky_generate)
    monkeypatch.setattr(
        "app.services.embedding_service.store_generated_faq_embeddings", fake_store
    )
    monkeypatch.setattr("app.composition.singletons.get_llm_service", lambda: object())
    monkeypatch.setattr(
        "app.composition.singletons.get_embedding_service", lambda: object()
    )

    faq_module.generate_and_store_faqs(["one", "bad", "two"], 42, 7)

    questions = [f["question"] for f in stored["faqs"]]
    assert questions == ["q-one", "q-two"]  # "bad" skipped, no exception
