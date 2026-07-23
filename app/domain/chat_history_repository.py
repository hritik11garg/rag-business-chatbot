from dataclasses import dataclass
from typing import List, Protocol


@dataclass(frozen=True)
class ChatMessage:
    """Read model for a stored chat turn — no ORM type crosses the port,
    so use cases and the summary task depend only on the domain, and stay
    trivially unit-testable (mirrors RefreshTokenRecord)."""

    role: str  # "user" | "assistant"
    message: str


class ChatHistoryRepository(Protocol):
    def get_recent_history(self, *, user_id: int) -> List[ChatMessage]: ...

    def save_message(
        self,
        *,
        user_id: int,
        organization_id: int,
        role: str,
        message: str,
    ) -> None: ...
