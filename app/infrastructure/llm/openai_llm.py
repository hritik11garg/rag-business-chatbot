from openai import OpenAI
from app.core.config import settings


class OpenAILLMService:
    """
    OpenAI-based LLM implementation.
    """

    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)

    def generate_answer(self, *, question: str, context: str) -> str:
        prompt = f"""
You are an enterprise business assistant.

You must answer ONLY using the provided company document context.
If the answer is not contained in the context, say:
"I could not find this information in the uploaded documents."

--------------------
Context:
{context}
--------------------

Question:
{question}
"""

        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a strict document-based assistant. Never invent answers.",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperature=0.1,
        )

        return response.choices[0].message.content
