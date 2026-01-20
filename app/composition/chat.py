from sqlalchemy.orm import Session

from app.use_cases.chat_with_kb import ChatWithKnowledgeBaseUseCase
from app.infrastructure.embeddings.sentence_transformer import (
    SentenceTransformerEmbeddingService,
)
from app.infrastructure.llm.openai_llm import OpenAILLMService
from app.infrastructure.db.chat_history_repository import DBChatHistoryRepository


def build_chat_use_case(db: Session) -> ChatWithKnowledgeBaseUseCase:
    return ChatWithKnowledgeBaseUseCase(
        embedding_service=SentenceTransformerEmbeddingService(),
        llm_service=OpenAILLMService(),
        chat_history=DBChatHistoryRepository(db),
        db=db,
    )
