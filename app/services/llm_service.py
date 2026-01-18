import requests


OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "llama3:8b"


def generate_answer(*, question: str, context: str) -> str:
    """
    Generate an answer using Ollama based on retrieved context.
    """

    prompt = f"""
You are a helpful business assistant.

Use ONLY the context below to answer the question.
If the answer is not in the context, say you don't know.

Context:
{context}

Question:
{question}

Answer:
""".strip()

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL_NAME,
            "prompt": prompt,
            "stream": False,
        },
        timeout=300,
    )

    response.raise_for_status()

    return response.json()["response"].strip()
