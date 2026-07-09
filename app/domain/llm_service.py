from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class GroundedAnswer:
    """An answer plus the model's self-assessed grounding confidence."""

    answer: str
    confidence: str  # "high" | "medium" | "low"


class LLMService(Protocol):
    """
    Abstraction for Large Language Model interactions.
    """

    def generate_answer(self, *, question: str, context: str) -> str:
        ...

    def generate_grounded_answer(
        self, *, question: str, context: str
    ) -> GroundedAnswer:
        ...
