from app.use_cases.chat_router import ChatRouterUseCase
from app.domain.intent_classifier import IntentClassifier
from app.use_cases.chitchat import ChitChatUseCase


class FakeKnowledgeUC:
    def execute(self, *, question, user):
        return {"answer": "KB answer"}


def test_chitchat_intent():
    router = ChatRouterUseCase(
        intent_classifier=IntentClassifier(),
        knowledge_uc=FakeKnowledgeUC(),
        chitchat_uc=ChitChatUseCase(),
    )

    result = router.execute(question="hello", user=None)
    assert result["answer"].startswith("Hi")
