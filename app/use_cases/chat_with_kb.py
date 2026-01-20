from app.db.models.user import User
from app.services.embedding_service import similarity_search
from app.domain.embedding_service import EmbeddingService
from app.domain.llm_service import LLMService
from app.domain.chat_history_repository import ChatHistoryRepository
from app.services.confidence import evaluate_confidence


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
        history_text = "\n".join(
            [f"{h.role.upper()}: {h.message}" for h in history]
        )

        full_context = f"""
Previous conversation:
{history_text}

Knowledge base context:
{context}
"""

        answer = self.llm_service.generate_answer(
            question=question,
            context=full_context,
        )

        confidence = evaluate_confidence(
            question=question,
            answer=answer,
            context=context,
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
            message=answer,
        )

        sources = list({row.filename for row in matches})

        return {
            "question": question,
            "answer": answer,
            "sources": sources,
            "confidence": confidence,
        }
