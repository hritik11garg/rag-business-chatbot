from app.db.models.user import User
from app.services.embedding_service import similarity_search
from app.domain.embedding_service import EmbeddingService
from app.domain.llm_service import LLMService
from app.domain.chat_history_repository import ChatHistoryRepository

# Rough prompt budget for injected chat history. The repository already
# caps the message COUNT, but messages have no length limit — this caps
# the SIZE so one long answer can't dominate the prompt.
# ~4 chars per token, so 2000 chars ≈ 500 tokens.
HISTORY_CHAR_BUDGET = 2000


def trim_history(history, *, budget: int = HISTORY_CHAR_BUDGET) -> str:
    """Render history newest-first within the budget, oldest dropped
    first. Messages are kept whole; the newest always survives."""
    kept = []
    total = 0
    for h in reversed(history):
        line = f"{h.role.upper()}: {h.message}"
        if kept and total + len(line) > budget:
            break
        kept.append(line)
        total += len(line)
    return "\n".join(reversed(kept))


class ChatWithKnowledgeBaseUseCase:
    def __init__(
        self,
        *,
        embedding_service: EmbeddingService,
        llm_service: LLMService,
        chat_history: ChatHistoryRepository,
        db,
    ):
        self.embedding_service = embedding_service
        self.llm_service = llm_service
        self.chat_history = chat_history
        self.db = db

    def execute(self, *, question: str, user: User) -> dict:
        query_embedding = self.embedding_service.embed_query(question)

        matches = similarity_search(
            db=self.db,
            organization_id=user.organization_id,
            query_embedding=query_embedding,
            limit=5,
        )

        if not matches:
            return {
                "question": question,
                "answer": "No relevant information found in the knowledge base.",
                "confidence": "low",
                "sources": [],
            }

        context = "\n\n".join([row.content for row in matches])

        history = self.chat_history.get_recent_history(user_id=user.id)
        history_text = trim_history(history)

        full_context = f"""
Previous conversation:
{history_text}

Knowledge base context:
{context}
"""

        # One LLM round-trip returns the answer AND its grounding
        # self-grade (was two sequential calls before Phase 3).
        result = self.llm_service.generate_grounded_answer(
            question=question,
            context=full_context,
        )

        self.chat_history.save_message(
            user_id=user.id,
            organization_id=user.organization_id,
            role="user",
            message=question,
        )

        self.chat_history.save_message(
            user_id=user.id,
            organization_id=user.organization_id,
            role="assistant",
            message=result.answer,
        )

        sources = list({row.filename for row in matches})

        return {
            "question": question,
            "answer": result.answer,
            "sources": sources,
            "confidence": result.confidence,
        }
