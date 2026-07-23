import logging
from typing import Callable, Iterator

from app.core.config import settings
from app.db.models.user import User
from app.services.embedding_service import similarity_search
from app.domain.embedding_service import EmbeddingService
from app.domain.llm_service import LLMService
from app.domain.chat_history_repository import ChatHistoryRepository
from app.domain.summary_repository import ConversationSummaryRepository
from app.prompts import split_confidence_marker

# Rough prompt budget for injected chat history. The repository already
# caps the message COUNT, but messages have no length limit — this caps
# the SIZE so one long answer can't dominate the prompt.
# ~4 chars per token, so 2000 chars ≈ 500 tokens.
HISTORY_CHAR_BUDGET = 2000

# While streaming, this many trailing characters are held back from the
# client so the CONFIDENCE marker line (max ~20 chars plus whitespace)
# is never emitted as answer text before we can parse it off.
STREAM_HOLDBACK = 40

NO_MATCH_ANSWER = "No relevant information found in the knowledge base."

logger = logging.getLogger(__name__)


def trim_history(history, *, budget: int = HISTORY_CHAR_BUDGET) -> str:
    """Render history newest-first within the budget, oldest dropped
    first. Messages are kept whole; the newest always survives."""
    kept = []
    total = 0
    for h in reversed(history):
        line = f"{h.role.upper()}: {h.message}"
        if kept and total + len(line) > budget:
            break
        kept.append(line)
        total += len(line)
    return "\n".join(reversed(kept))


class ChatWithKnowledgeBaseUseCase:
    def __init__(
        self,
        *,
        embedding_service: EmbeddingService,
        llm_service: LLMService,
        chat_history: ChatHistoryRepository,
        db,
        summary_repo: ConversationSummaryRepository | None = None,
        schedule_summary_update: Callable[[int, int], None] | None = None,
    ):
        self.embedding_service = embedding_service
        self.llm_service = llm_service
        self.chat_history = chat_history
        self.db = db
        # Summary memory is an enhancement, not a correctness
        # dependency: with no repo/scheduler wired, chat still works on
        # raw recent history alone.
        self.summary_repo = summary_repo
        self.schedule_summary_update = schedule_summary_update

    def _retrieve(
        self,
        *,
        question: str,
        user: User,
        top_k: int,
        document_ids: list[int] | None,
    ):
        query_embedding = self.embedding_service.embed_query(question)
        return similarity_search(
            db=self.db,
            organization_id=user.organization_id,
            query_embedding=query_embedding,
            limit=top_k,
            document_ids=document_ids,
        )

    def _build_full_context(self, *, user: User, matches) -> str:
        context = "\n\n".join([row.content for row in matches])
        history = self.chat_history.get_recent_history(user_id=user.id)
        history_text = trim_history(history)

        # Long-term memory: a compact rolling summary maintained
        # asynchronously. It may lag the latest exchange (the update
        # task runs after we answer) — the raw recent history above
        # covers that gap.
        summary_block = ""
        if self.summary_repo:
            summary = self.summary_repo.get_summary(user_id=user.id)
            if summary:
                summary_block = (
                    f"Important facts from earlier conversation:\n{summary}\n\n"
                )

        return f"""
{summary_block}Previous conversation:
{history_text}

Knowledge base context:
{context}
"""

    def _save_exchange(self, *, user: User, question: str, answer: str):
        self.chat_history.save_message(
            user_id=user.id,
            organization_id=user.organization_id,
            role="user",
            message=question,
        )
        self.chat_history.save_message(
            user_id=user.id,
            organization_id=user.organization_id,
            role="assistant",
            message=answer,
        )
        if self.schedule_summary_update:
            try:
                self.schedule_summary_update(user.id, user.organization_id)
            except Exception:  # broker down must never fail the answer
                logger.warning("summary update not scheduled", exc_info=True)

    def execute(
        self,
        *,
        question: str,
        user: User,
        top_k: int = settings.DEFAULT_TOP_K,
        document_ids: list[int] | None = None,
    ) -> dict:
        matches = self._retrieve(
            question=question, user=user, top_k=top_k, document_ids=document_ids
        )

        if not matches:
            return {
                "question": question,
                "answer": NO_MATCH_ANSWER,
                "confidence": "low",
                "sources": [],
            }

        full_context = self._build_full_context(user=user, matches=matches)

        # One LLM round-trip returns the answer AND its grounding
        # self-grade (was two sequential calls before Phase 3).
        result = self.llm_service.generate_grounded_answer(
            question=question,
            context=full_context,
        )

        self._save_exchange(user=user, question=question, answer=result.answer)

        sources = list({row.filename for row in matches})

        return {
            "question": question,
            "answer": result.answer,
            "sources": sources,
            "confidence": result.confidence,
        }

    def execute_stream(
        self,
        *,
        question: str,
        user: User,
        top_k: int = settings.DEFAULT_TOP_K,
        document_ids: list[int] | None = None,
    ) -> Iterator[tuple[str, dict]]:
        """Streaming variant: yields ("token", {"text": ...}) events as
        the model produces them, then one ("done", {sources, confidence}).

        The last STREAM_HOLDBACK chars are buffered so the trailing
        CONFIDENCE marker is parsed off instead of reaching the client.
        HTTP concerns (SSE framing) live in the route, not here.
        """
        matches = self._retrieve(
            question=question, user=user, top_k=top_k, document_ids=document_ids
        )

        if not matches:
            yield "token", {"text": NO_MATCH_ANSWER}
            yield "done", {"sources": [], "confidence": "low"}
            return

        full_context = self._build_full_context(user=user, matches=matches)

        emitted: list[str] = []
        buffer = ""
        for fragment in self.llm_service.stream_grounded_answer(
            question=question, context=full_context
        ):
            buffer += fragment
            if len(buffer) > STREAM_HOLDBACK:
                text, buffer = buffer[:-STREAM_HOLDBACK], buffer[-STREAM_HOLDBACK:]
                emitted.append(text)
                yield "token", {"text": text}

        tail, confidence = split_confidence_marker(buffer)
        if tail:
            emitted.append(tail)
            yield "token", {"text": tail}

        answer = "".join(emitted).strip()
        self._save_exchange(user=user, question=question, answer=answer)

        sources = list({row.filename for row in matches})
        yield "done", {"sources": sources, "confidence": confidence}
