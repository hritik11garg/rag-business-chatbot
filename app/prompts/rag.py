"""Prompts and response parsing for the /chat answering path."""
import json

from app.domain.llm_service import GroundedAnswer

SYSTEM_PROMPT = "You are a strict document-based assistant. Never invent answers."

RAG_ANSWER_TEMPLATE = """
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

GROUNDED_ANSWER_TEMPLATE = """
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


# Streaming can't use the JSON contract above — JSON is only parseable
# once complete, so tokens couldn't be forwarded as they arrive. The
# streamed variant emits plain text and ends with a marker line that
# the caller strips off and parses (see split_confidence_marker).
STREAMED_GROUNDED_TEMPLATE = """
You are an enterprise business assistant.

You must answer ONLY using the provided company document context.
If the answer is not contained in the context, the answer must be:
"I could not find this information in the uploaded documents."

--------------------
Context:
{context}
--------------------

Question:
{question}

Write your answer as plain text (no JSON, no markdown fences).
Then, on its own final line, rate how well your answer is supported
by the context by writing exactly one of:
CONFIDENCE: HIGH
CONFIDENCE: MEDIUM
CONFIDENCE: LOW
(HIGH = directly supported in context, MEDIUM = partially supported
or inferred, LOW = not supported or weak.)
"""


def build_rag_prompt(*, question: str, context: str) -> str:
    return RAG_ANSWER_TEMPLATE.format(question=question, context=context)


def build_grounded_rag_prompt(*, question: str, context: str) -> str:
    """RAG prompt that asks for the answer AND a grounding self-grade
    in one response, so /chat costs one LLM round-trip, not two."""
    return GROUNDED_ANSWER_TEMPLATE.format(question=question, context=context)


def build_streamed_grounded_prompt(*, question: str, context: str) -> str:
    """Streaming counterpart of build_grounded_rag_prompt."""
    return STREAMED_GROUNDED_TEMPLATE.format(question=question, context=context)


_VALID_CONFIDENCE = {"high", "medium", "low"}

CONFIDENCE_MARKER = "CONFIDENCE:"


def split_confidence_marker(text: str) -> tuple[str, str]:
    """Split streamed output into (answer, confidence).

    Parses the trailing marker line of STREAMED_GROUNDED_TEMPLATE. If
    the model skipped or mangled the marker, the whole text is the
    answer and confidence falls back to "low" — same never-fail policy
    as parse_grounded_answer.
    """
    idx = text.rfind(CONFIDENCE_MARKER)
    if idx != -1:
        level = text[idx + len(CONFIDENCE_MARKER):].strip().strip(".").lower()
        if level in _VALID_CONFIDENCE:
            return text[:idx].rstrip(), level
    return text.rstrip(), "low"


def parse_grounded_answer(raw: str) -> GroundedAnswer:
    """Parse the JSON contract of GROUNDED_ANSWER_TEMPLATE.

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
