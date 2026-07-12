from dataclasses import dataclass
from typing import Iterator, Protocol


@dataclass(frozen=True)
class GroundedAnswer:
    """An answer plus the model's self-assessed grounding confidence."""

    answer: str
    confidence: str  # "high" | "medium" | "low"


class LLMService(Protocol):
    """
    Abstraction for Large Language Model interactions.
    """

    def generate_answer(self, *, question: str, context: str) -> str: ...

    def generate_grounded_answer(
        self, *, question: str, context: str
    ) -> GroundedAnswer: ...

    def stream_grounded_answer(self, *, question: str, context: str) -> Iterator[str]:
        """Yield the answer as text fragments. The stream ends with a
        CONFIDENCE marker line the caller parses off (see
        app.prompts.split_confidence_marker)."""
        ...
