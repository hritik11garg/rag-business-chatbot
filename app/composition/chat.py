from sqlalchemy.orm import Session

from app.use_cases.chat_router import ChatRouterUseCase
from app.use_cases.chat_with_kb import ChatWithKnowledgeBaseUseCase
from app.use_cases.chitchat import ChitChatUseCase
from app.domain.intent_classifier import IntentClassifier

from app.infrastructure.embeddings.sentence_transformer import (
    SentenceTransformerEmbeddingService,
)
from app.infrastructure.llm.factory import build_llm_service
from app.infrastructure.db.chat_history_repository import DBChatHistoryRepository
from app.services.confidence import ConfidenceEvaluator


def build_chat_router_use_case(db: Session) -> ChatRouterUseCase:
    llm_service = build_llm_service()

    knowledge_uc = ChatWithKnowledgeBaseUseCase(
        embedding_service=SentenceTransformerEmbeddingService(),
        llm_service=llm_service,
        confidence_evaluator=ConfidenceEvaluator(llm_service=llm_service),
        chat_history=DBChatHistoryRepository(db),
        db=db,
    )

    return ChatRouterUseCase(
        intent_classifier=IntentClassifier(),
        knowledge_uc=knowledge_uc,
        chitchat_uc=ChitChatUseCase(),
    )
