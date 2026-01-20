from typing import Protocol, List
from app.db.models.chat_history import ChatHistory


class ChatHistoryRepository(Protocol):
    def get_recent_history(self, *, user_id: int) -> List[ChatHistory]:
        ...

    def save_message(
        self,
        *,
        user_id: int,
        organization_id: int,
        role: str,
        message: str,
    ) -> None:
        ...
