from sqlalchemy.orm import Session

from app.use_cases.chat_router import ChatRouterUseCase
from app.use_cases.chat_with_kb import ChatWithKnowledgeBaseUseCase
from app.use_cases.chitchat import ChitChatUseCase
from app.domain.intent_classifier import IntentClassifier

from app.infrastructure.embeddings.sentence_transformer import (
    SentenceTransformerEmbeddingService,
)
from app.infrastructure.llm.openai_llm import OpenAILLMService
from app.infrastructure.db.chat_history_repository import DBChatHistoryRepository


def build_chat_router_use_case(db: Session) -> ChatRouterUseCase:
    knowledge_uc = ChatWithKnowledgeBaseUseCase(
        embedding_service=SentenceTransformerEmbeddingService(),
        llm_service=OpenAILLMService(),
        chat_history=DBChatHistoryRepository(db),
        db=db,
    )

    return ChatRouterUseCase(
        intent_classifier=IntentClassifier(),
        knowledge_uc=knowledge_uc,
        chitchat_uc=ChitChatUseCase(),
    )
