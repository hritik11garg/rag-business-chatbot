from openai import OpenAI
from app.core.config import settings

# Load API key from environment
client = OpenAI(api_key=settings.OPENAI_API_KEY)

def generate_answer(question: str, context: str) -> str:
    """
    Generate an answer strictly from retrieved document context using OpenAI.
    """

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

    response = client.chat.completions.create(
        model="gpt-4o-mini",  # fast + cheap + strong for RAG
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


# def generate_answer(*, question: str, context: str) -> str:
#     """
#     Generate answer using Gemini with optional RAG context.
#     """

#     prompt = f"""
#     You are an AI assistant answering questions strictly from provided context.

#     Use ONLY the context below to answer the question.
#     If the answer is not in the context, say you don't know.

#     Context:
#     {context}

#     Question:
#     {question}

#     Answer:
#     """.strip()
#     response = client.models.generate_content(
#         model="gemini-2.5-flash",
#         contents=prompt,
#     )

#     return response.text
