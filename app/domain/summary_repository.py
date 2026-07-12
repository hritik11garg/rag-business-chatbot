from typing import Protocol


class ConversationSummaryRepository(Protocol):
    def get_summary(self, *, user_id: int) -> str | None: ...

    def upsert_summary(
        self, *, user_id: int, organization_id: int, summary: str
    ) -> None: ...
