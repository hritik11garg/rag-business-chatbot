from app.use_cases.chat_with_kb import ChatWithKnowledgeBaseUseCase
from app.db.models.user import User


class FakeEmbeddingService:
    def embed_query(self, text: str):
        return [0.1, 0.2, 0.3]


class FakeLLMService:
    def generate_answer(self, *, question: str, context: str) -> str:
        return "Acme Corp is a software company providing SaaS products."


class FakeChatHistoryRepository:
    def __init__(self):
        self.saved = []

    def get_recent_history(self, *, user_id: int):
        return []

    def save_message(self, *, user_id, organization_id, role, message):
        self.saved.append((role, message))


class FakeRetrievalResult:
    def __init__(self, content, filename):
        self.content = content
        self.filename = filename


def fake_similarity_search(*, db, organization_id, query_embedding, limit):
    return [
        FakeRetrievalResult(
            content="About Acme Corp. Acme Corp is a SaaS company.",
            filename="company.pdf",
        )
    ]


def test_chat_returns_company_description(monkeypatch):
    monkeypatch.setattr(
        "app.use_cases.chat_with_kb.similarity_search",
        fake_similarity_search,
    )

    user = User(
        id=1,
        email="test@acme.com",
        hashed_password="x",
        organization_id=1,
        is_active=True,
    )

    use_case = ChatWithKnowledgeBaseUseCase(
        embedding_service=FakeEmbeddingService(),
        llm_service=FakeLLMService(),
        chat_history=FakeChatHistoryRepository(),
        db=None,
    )

    result = use_case.execute(question="about", user=user)

    assert "Acme Corp" in result["answer"]
    assert result["sources"] == ["company.pdf"]
