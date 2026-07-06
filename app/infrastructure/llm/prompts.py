"""
Prompts shared by every LLM adapter.

Kept in one place so that switching providers changes *who* we ask,
never *what* we ask — all providers must behave identically.
(A full prompt-templating module is planned in Phase 4.)
"""

SYSTEM_PROMPT = "You are a strict document-based assistant. Never invent answers."


def build_rag_prompt(*, question: str, context: str) -> str:
    return f"""
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
