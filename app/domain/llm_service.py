from typing import Protocol


class LLMService(Protocol):
    """
    Abstraction for Large Language Model interactions.
    """

    def generate_answer(self, *, question: str, context: str) -> str:
        ...
