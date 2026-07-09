"""
Prompts and response parsing shared by every LLM adapter.

Kept in one place so that switching providers changes *who* we ask,
never *what* we ask — all providers must behave identically.
(A full prompt-templating module is planned in Phase 4.)
"""
import json

from app.domain.llm_service import GroundedAnswer

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


def build_grounded_rag_prompt(*, question: str, context: str) -> str:
    """RAG prompt that asks for the answer AND a grounding self-grade
    in one response, so /chat costs one LLM round-trip, not two."""
    return f"""
You are an enterprise business assistant.

You must answer ONLY using the provided company document context.
If the answer is not contained in the context, the answer must be:
"I could not find this information in the uploaded documents."

Also rate how well your answer is supported by the context:
HIGH = directly supported in context
MEDIUM = partially supported / inferred
LOW = not supported or weak

--------------------
Context:
{context}
--------------------

Question:
{question}

Return STRICT JSON and nothing else:
{{"answer": "<your answer>", "confidence": "HIGH|MEDIUM|LOW"}}
"""


_VALID_CONFIDENCE = {"high", "medium", "low"}


def parse_grounded_answer(raw: str) -> GroundedAnswer:
    """Parse the JSON contract of build_grounded_rag_prompt.

    If the model breaks the format, the raw text is kept as the answer
    and confidence falls back to "low" — never a 500 for the user.
    """
    text = raw.strip()
    if text.startswith("```"):
        # some models wrap JSON in markdown fences despite instructions
        text = text.strip("`").strip()
        if text.lower().startswith("json"):
            text = text[4:]
    try:
        data = json.loads(text)
        answer = str(data["answer"]).strip()
        confidence = str(data["confidence"]).strip().lower()
        if not answer or confidence not in _VALID_CONFIDENCE:
            raise ValueError("missing answer or invalid confidence")
        return GroundedAnswer(answer=answer, confidence=confidence)
    except (ValueError, KeyError, TypeError):
        return GroundedAnswer(answer=raw.strip(), confidence="low")
