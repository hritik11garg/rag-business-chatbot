from sqlalchemy.orm import Session
from app.db.models.user import User

from app.services.chat_memory import get_recent_history, save_message
from app.infrastructure.embeddings.sentence_transformer import (
    SentenceTransformerEmbeddingService,
)
from app.services.embedding_service import similarity_search
from app.services.llm_service import generate_answer
from app.services.confidence import evaluate_confidence


class ChatWithKnowledgeBaseUseCase:
    def __init__(self, db: Session):
        self.db = db

    def execute(self, *, question: str, user: User) -> dict:
        # Step 1: Embed query
        embedding_service = SentenceTransformerEmbeddingService()

        query_embedding = embedding_service.embed_query(question)

        # Step 2: Retrieve relevant chunks
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

        # Step 3: Build context
        context = "\n\n".join([row.content for row in matches])

        history = get_recent_history(self.db, user_id=user.id)
        history_text = "\n".join(
            [f"{h.role.upper()}: {h.message}" for h in history]
        )

        full_context = f"""
Previous conversation:
{history_text}

Knowledge base context:
{context}
"""

        # Step 4: Generate answer
        answer = generate_answer(
            question=question,
            context=full_context,
        )

        confidence = evaluate_confidence(
            question=question,
            answer=answer,
            context=context,
        )

        # Step 5: Save messages
        save_message(
            self.db,
            user_id=user.id,
            organization_id=user.organization_id,
            role="user",
            message=question,
        )

        save_message(
            self.db,
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
