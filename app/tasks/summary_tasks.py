from app.core.celery_app import celery


@celery.task(name="app.tasks.update_summary_task")
def update_summary_task(user_id: int, organization_id: int):
    """Merge the user's recent chat history into their rolling summary.

    Runs off the critical path after each exchange, so /chat latency
    never pays for the extra LLM call. The task re-reads history from
    the DB (instead of taking the exchange as arguments) so a retried
    or delayed run still summarizes the latest state.
    """
    from app.composition.singletons import get_llm_service
    from app.db.session import SessionLocal
    from app.infrastructure.db.chat_history_repository import (
        DBChatHistoryRepository,
    )
    from app.infrastructure.db.summary_repository import (
        DBConversationSummaryRepository,
    )
    from app.prompts.summary import build_summary_update_prompt, clamp_summary

    db = SessionLocal()
    try:
        history = DBChatHistoryRepository(db).get_recent_history(user_id=user_id)
        if not history:
            return

        repo = DBConversationSummaryRepository(db)
        current = repo.get_summary(user_id=user_id) or ""
        transcript = "\n".join(f"{h.role.upper()}: {h.message}" for h in history)

        prompt = build_summary_update_prompt(
            current_summary=current, transcript=transcript
        )
        updated = clamp_summary(
            get_llm_service().generate_answer(question=prompt, context="")
        )

        if updated and updated != current:
            repo.upsert_summary(
                user_id=user_id,
                organization_id=organization_id,
                summary=updated,
            )
    finally:
        db.close()
