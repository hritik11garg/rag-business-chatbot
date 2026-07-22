from typing import Iterator

from anthropic import Anthropic

from app.domain.llm_service import GroundedAnswer
from app.prompts import (
    SYSTEM_PROMPT,
    build_grounded_rag_prompt,
    build_rag_prompt,
    build_streamed_grounded_prompt,
    parse_grounded_answer,
)


class AnthropicLLMService:
    """
    Claude adapter. Anthropic's Messages API is not OpenAI-compatible
    (own SDK, system prompt is a top-level parameter, max_tokens is
    required), so it gets a dedicated adapter instead of a base_url swap.
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        temperature: float = 0.1,
        max_tokens: int = 1024,
    ):
        self.client = Anthropic(api_key=api_key)
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def generate_answer(self, *, question: str, context: str) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": build_rag_prompt(question=question, context=context),
                }
            ],
            temperature=self.temperature,
        )
        return response.content[0].text

    def generate_grounded_answer(
        self, *, question: str, context: str
    ) -> GroundedAnswer:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": build_grounded_rag_prompt(
                        question=question, context=context
                    ),
                }
            ],
            temperature=self.temperature,
        )
        return parse_grounded_answer(response.content[0].text)

    def stream_grounded_answer(self, *, question: str, context: str) -> Iterator[str]:
        with self.client.messages.stream(
            model=self.model,
            max_tokens=self.max_tokens,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": build_streamed_grounded_prompt(
                        question=question, context=context
                    ),
                }
            ],
            temperature=self.temperature,
        ) as stream:
            yield from stream.text_stream
