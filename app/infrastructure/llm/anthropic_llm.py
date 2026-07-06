from anthropic import Anthropic

from app.infrastructure.llm.prompts import SYSTEM_PROMPT, build_rag_prompt


class AnthropicLLMService:
    """
    Claude adapter. Anthropic's Messages API is not OpenAI-compatible
    (own SDK, system prompt is a top-level parameter, max_tokens is
    required), so it gets a dedicated adapter instead of a base_url swap.
    """

    def __init__(self, *, api_key: str, model: str, temperature: float = 0.1):
        self.client = Anthropic(api_key=api_key)
        self.model = model
        self.temperature = temperature

    def generate_answer(self, *, question: str, context: str) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
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
