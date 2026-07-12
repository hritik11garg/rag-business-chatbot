"""Prompt and response parsing for background FAQ generation."""

import json

FAQ_GENERATION_TEMPLATE = """
You are generating FAQs from business documentation.

From the following text, generate 3 clear customer-facing FAQ question and answer pairs.

Rules:
- Questions must be realistic user questions
- Answers must be directly based on the text
- Keep them short and factual
- Output STRICT JSON list format:

[
{{"question": "...", "answer": "..."}},
{{"question": "...", "answer": "..."}}
]

Text:
{chunk}
"""


def build_faq_generation_prompt(*, chunk: str) -> str:
    return FAQ_GENERATION_TEMPLATE.format(chunk=chunk)


def parse_faq_response(raw: str) -> list[dict]:
    """Parse the JSON-list contract of FAQ_GENERATION_TEMPLATE.

    A broken response yields an empty list — the task skips the chunk
    rather than failing the whole document.
    """
    try:
        faqs = json.loads(raw)
    except (ValueError, TypeError):
        return []
    if not isinstance(faqs, list):
        return []
    return [
        f for f in faqs if isinstance(f, dict) and "question" in f and "answer" in f
    ]
