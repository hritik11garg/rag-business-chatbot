from app.use_cases.chat_with_kb import ChatWithKnowledgeBaseUseCase
from app.db.models.user import User


# ---------- FAKES ----------

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

    def save_message(
        self,
        *,
        user_id: int,
        organization_id: int,
        role: str,
        message: str,
    ):
        self.saved.append((role, message))


class FakeRetrievalResult:
    def __init__(self, content: str, filename: str):
        self.content = content
        self.filename = filename


def fake_similarity_search(*, db, organization_id, query_embedding, limit):
    return [
        FakeRetrievalResult(
            content="About Acme Corp. Acme Corp is a SaaS company.",
            filename="company.pdf",
        )
    ]


# ---------- TEST ----------

def test_chat_returns_company_description(monkeypatch):
    # Patch similarity search
    monkeypatch.setattr(
        "app.use_cases.chat_with_kb.similarity_search",
        fake_similarity_search,
    )

    # Fake user
    user = User(
        id=1,
        email="test@acme.com",
        hashed_password="x",
        organization_id=1,
        is_active=True,
    )

    # Build use case with fakes
    use_case = ChatWithKnowledgeBaseUseCase.__new__(ChatWithKnowledgeBaseUseCase)
    use_case.db = None
    use_case.embedding_service = FakeEmbeddingService()
    use_case.llm_service = FakeLLMService()
    use_case.chat_history = FakeChatHistoryRepository()

    # Execute
    result = use_case.execute(question="about", user=user)

    # Assertions
    assert "Acme Corp" in result["answer"]
    assert result["confidence"] in ("high", "medium")
    assert result["sources"] == ["company.pdf"]
