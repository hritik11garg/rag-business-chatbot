import app.use_cases.chat_with_kb as chat_module
from app.use_cases.chat_with_kb import ChatWithKnowledgeBaseUseCase
from app.db.models.user import User

ANSWER = "Acme Corp provides SaaS products to enterprise clients."


class FakeEmbeddingService:
    def embed_query(self, text: str):
        return [0.1, 0.2, 0.3]


class FakeStreamingLLMService:
    def stream_grounded_answer(self, *, question: str, context: str):
        # tiny fragments on purpose: the CONFIDENCE marker must survive
        # being split across chunk boundaries
        full = f"{ANSWER}\nCONFIDENCE: MEDIUM"
        for i in range(0, len(full), 7):
            yield full[i : i + 7]


class FakeChatHistoryRepository:
    def __init__(self):
        self.saved = []

    def get_recent_history(self, *, user_id: int):
        return []

    def save_message(self, *, user_id, organization_id, role, message):
        self.saved.append((role, message))


class FakeRetrievalResult:
    content = "About Acme Corp. Acme Corp is a SaaS company."
    filename = "company.pdf"


class FakeSummaryRepo:
    def __init__(self, summary=None):
        self.summary = summary

    def get_summary(self, *, user_id: int):
        return self.summary


def make_use_case(monkeypatch, **overrides):
    monkeypatch.setattr(
        chat_module,
        "similarity_search",
        lambda **kwargs: [FakeRetrievalResult()],
    )
    defaults = dict(
        embedding_service=FakeEmbeddingService(),
        llm_service=FakeStreamingLLMService(),
        chat_history=FakeChatHistoryRepository(),
        db=None,
    )
    defaults.update(overrides)
    return ChatWithKnowledgeBaseUseCase(**defaults)


def make_user():
    return User(
        id=1,
        email="test@acme.com",
        hashed_password="x",
        organization_id=1,
        is_active=True,
    )


def test_stream_emits_answer_without_confidence_marker(monkeypatch):
    history = FakeChatHistoryRepository()
    use_case = make_use_case(monkeypatch, chat_history=history)

    events = list(use_case.execute_stream(question="about acme", user=make_user()))

    tokens = "".join(d["text"] for e, d in events if e == "token")
    assert tokens.strip() == ANSWER
    assert "CONFIDENCE" not in tokens

    done_events = [d for e, d in events if e == "done"]
    assert done_events == [{"sources": ["company.pdf"], "confidence": "medium"}]
    assert events[-1][0] == "done"

    # the assembled answer (not the marker) is what history records
    assert history.saved == [
        ("user", "about acme"),
        ("assistant", ANSWER),
    ]


def test_stream_schedules_summary_update(monkeypatch):
    scheduled = []
    use_case = make_use_case(
        monkeypatch,
        schedule_summary_update=lambda user_id, org_id: scheduled.append(
            (user_id, org_id)
        ),
    )

    list(use_case.execute_stream(question="about acme", user=make_user()))

    assert scheduled == [(1, 1)]


def test_stream_survives_broken_summary_scheduler(monkeypatch):
    def boom(user_id, org_id):
        raise ConnectionError("broker down")

    use_case = make_use_case(monkeypatch, schedule_summary_update=boom)

    events = list(use_case.execute_stream(question="about acme", user=make_user()))
    assert events[-1][0] == "done"  # answer still completed


def test_summary_injected_into_context(monkeypatch):
    captured = {}

    class CapturingLLM(FakeStreamingLLMService):
        def stream_grounded_answer(self, *, question, context):
            captured["context"] = context
            yield from super().stream_grounded_answer(
                question=question, context=context
            )

    use_case = make_use_case(
        monkeypatch,
        llm_service=CapturingLLM(),
        summary_repo=FakeSummaryRepo("User is evaluating Acme for a 50-seat team."),
    )

    list(use_case.execute_stream(question="about acme", user=make_user()))

    assert "Important facts from earlier conversation:" in captured["context"]
    assert "50-seat team" in captured["context"]


def test_no_summary_block_when_repo_empty(monkeypatch):
    captured = {}

    class CapturingLLM(FakeStreamingLLMService):
        def stream_grounded_answer(self, *, question, context):
            captured["context"] = context
            yield from super().stream_grounded_answer(
                question=question, context=context
            )

    use_case = make_use_case(
        monkeypatch, llm_service=CapturingLLM(), summary_repo=FakeSummaryRepo(None)
    )

    list(use_case.execute_stream(question="about acme", user=make_user()))

    assert "Important facts" not in captured["context"]
