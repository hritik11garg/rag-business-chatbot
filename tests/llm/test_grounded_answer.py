from app.infrastructure.llm.prompts import parse_grounded_answer
from app.use_cases.chat_with_kb import trim_history


class Msg:
    def __init__(self, role, message):
        self.role = role
        self.message = message


def test_parse_valid_json():
    result = parse_grounded_answer(
        '{"answer": "Refunds take 14 days.", "confidence": "HIGH"}'
    )
    assert result.answer == "Refunds take 14 days."
    assert result.confidence == "high"


def test_parse_json_wrapped_in_markdown_fences():
    raw = '```json\n{"answer": "Refunds take 14 days.", "confidence": "medium"}\n```'
    result = parse_grounded_answer(raw)
    assert result.answer == "Refunds take 14 days."
    assert result.confidence == "medium"


def test_parse_broken_output_falls_back_to_raw_text():
    raw = "Refunds take 14 days, according to the policy document."
    result = parse_grounded_answer(raw)
    assert result.answer == raw
    assert result.confidence == "low"


def test_parse_invalid_confidence_falls_back():
    raw = '{"answer": "Refunds take 14 days.", "confidence": "very high"}'
    result = parse_grounded_answer(raw)
    assert result.answer == raw
    assert result.confidence == "low"


def test_trim_history_keeps_everything_under_budget():
    history = [Msg("user", "hi"), Msg("assistant", "hello")]
    assert trim_history(history) == "USER: hi\nASSISTANT: hello"


def test_trim_history_drops_oldest_first():
    history = [
        Msg("user", "old " * 100),
        Msg("assistant", "also old " * 100),
        Msg("user", "newest question"),
    ]
    text = trim_history(history, budget=50)
    assert text == "USER: newest question"


def test_trim_history_always_keeps_newest_even_if_over_budget():
    history = [Msg("assistant", "x" * 500)]
    assert trim_history(history, budget=50) == "ASSISTANT: " + "x" * 500
