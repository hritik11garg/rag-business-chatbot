from sqlalchemy.orm import Session

from app.use_cases.chat_router import ChatRouterUseCase
from app.use_cases.chat_with_kb import ChatWithKnowledgeBaseUseCase
from app.use_cases.chitchat import ChitChatUseCase
from app.domain.intent_classifier import IntentClassifier

from app.composition.singletons import get_embedding_service, get_llm_service
from app.infrastructure.db.chat_history_repository import DBChatHistoryRepository
from app.infrastructure.db.summary_repository import (
    DBConversationSummaryRepository,
)
from app.tasks.summary_tasks import update_summary_task


def build_chat_router_use_case(db: Session) -> ChatRouterUseCase:
    knowledge_uc = ChatWithKnowledgeBaseUseCase(
        embedding_service=get_embedding_service(),
        llm_service=get_llm_service(),
        chat_history=DBChatHistoryRepository(db),
        db=db,
        summary_repo=DBConversationSummaryRepository(db),
        schedule_summary_update=lambda user_id, org_id: update_summary_task.delay(
            user_id, org_id
        ),
    )

    return ChatRouterUseCase(
        intent_classifier=IntentClassifier(),
        knowledge_uc=knowledge_uc,
        chitchat_uc=ChitChatUseCase(),
    )
