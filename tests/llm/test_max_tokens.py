"""The LLM output cap (LLM_MAX_TOKENS) must actually reach the provider.

Unbounded generation is what lets a verbose answer blow past the latency
budget and inflate per-request cost, so the cap is only useful if every
call carries it. A fake OpenAI client captures the kwargs — no network,
no key.
"""

from app.infrastructure.llm.openai_compatible import OpenAICompatibleLLMService


class _Capture:
    """Records the kwargs of the last chat.completions.create call and
    returns a minimal grounded-answer-shaped response."""

    def __init__(self):
        self.calls = []

        class _Completions:
            def create(_self, **kwargs):
                self.calls.append(kwargs)
                if kwargs.get("stream"):
                    return iter(())  # empty stream is fine for this assertion

                class _Msg:
                    content = '{"answer": "ok", "confidence": "high"}'

                class _Choice:
                    message = _Msg()

                class _Resp:
                    choices = [_Choice()]

                return _Resp()

        class _Chat:
            completions = _Completions()

        self.chat = _Chat()


def _service(monkeypatch, max_tokens):
    svc = OpenAICompatibleLLMService.__new__(OpenAICompatibleLLMService)
    svc.client = _Capture()
    svc.model = "test-model"
    svc.temperature = 0.1
    svc.max_tokens = max_tokens
    return svc


def test_generate_answer_sends_max_tokens(monkeypatch):
    svc = _service(monkeypatch, 321)
    svc.generate_answer(question="q", context="c")
    assert svc.client.calls[-1]["max_tokens"] == 321


def test_grounded_answer_sends_max_tokens(monkeypatch):
    svc = _service(monkeypatch, 256)
    svc.generate_grounded_answer(question="q", context="c")
    assert svc.client.calls[-1]["max_tokens"] == 256


def test_stream_sends_max_tokens(monkeypatch):
    svc = _service(monkeypatch, 200)
    list(svc.stream_grounded_answer(question="q", context="c"))
    call = svc.client.calls[-1]
    assert call["max_tokens"] == 200
    assert call["stream"] is True


def test_factory_wires_the_configured_cap(monkeypatch):
    """The factory must pass settings.LLM_MAX_TOKENS into the adapter, or
    the cap is dead config."""
    from app.core.config import settings
    from app.infrastructure.llm import factory

    monkeypatch.setattr(settings, "LLM_PROVIDER", "groq")
    monkeypatch.setattr(settings, "GROQ_API_KEY", "test-key")
    monkeypatch.setattr(settings, "LLM_MAX_TOKENS", 288)

    svc = factory.build_llm_service()
    assert svc.max_tokens == 288
