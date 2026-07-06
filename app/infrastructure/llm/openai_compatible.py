from openai import OpenAI

from app.infrastructure.llm.prompts import SYSTEM_PROMPT, build_rag_prompt


class OpenAICompatibleLLMService:
    """
    LLM adapter for any provider that speaks the OpenAI chat-completions
    API: OpenAI itself, Groq, Google Gemini (via its OpenAI-compatible
    endpoint), and local Ollama. The provider is selected purely by
    base_url + api_key + model — no per-provider code needed.
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str | None = None,
        temperature: float = 0.1,
    ):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.temperature = temperature

    def generate_answer(self, *, question: str, context: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": build_rag_prompt(question=question, context=context),
                },
            ],
            temperature=self.temperature,
        )
        return response.choices[0].message.content
