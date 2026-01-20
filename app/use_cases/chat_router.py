from app.domain.intent import ChatIntent
from app.domain.intent_classifier import IntentClassifier
from app.use_cases.chat_with_kb import ChatWithKnowledgeBaseUseCase
from app.use_cases.chitchat import ChitChatUseCase
from app.db.models.user import User


class ChatRouterUseCase:
    def __init__(
        self,
        *,
        intent_classifier: IntentClassifier,
        knowledge_uc: ChatWithKnowledgeBaseUseCase,
        chitchat_uc: ChitChatUseCase,
    ):
        self.intent_classifier = intent_classifier
        self.knowledge_uc = knowledge_uc
        self.chitchat_uc = chitchat_uc

    def execute(self, *, question: str, user: User) -> dict:
        intent = self.intent_classifier.classify(question)

        if intent == ChatIntent.CHITCHAT:
            return self.chitchat_uc.execute(question=question)

        if intent == ChatIntent.KNOWLEDGE:
            return self.knowledge_uc.execute(question=question, user=user)

        return {
            "question": question,
            "answer": "I can’t help with that request.",
            "sources": [],
            "confidence": "low",
        }
