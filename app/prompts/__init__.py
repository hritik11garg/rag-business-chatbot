"""
Every prompt the system sends to an LLM, in one place.

Templates are named module-level constants (inspectable and testable);
builder functions fill their variables. Adapters and services import
from here so that switching providers changes *who* we ask, never
*what* we ask — all providers must behave identically.
"""
from app.prompts.rag import (
    SYSTEM_PROMPT,
    RAG_ANSWER_TEMPLATE,
    GROUNDED_ANSWER_TEMPLATE,
    STREAMED_GROUNDED_TEMPLATE,
    build_rag_prompt,
    build_grounded_rag_prompt,
    build_streamed_grounded_prompt,
    parse_grounded_answer,
    split_confidence_marker,
)
from app.prompts.faq import (
    FAQ_GENERATION_TEMPLATE,
    build_faq_generation_prompt,
    parse_faq_response,
)
from app.prompts.summary import (
    SUMMARY_CHAR_LIMIT,
    SUMMARY_UPDATE_TEMPLATE,
    build_summary_update_prompt,
    clamp_summary,
)

__all__ = [
    "SYSTEM_PROMPT",
    "RAG_ANSWER_TEMPLATE",
    "GROUNDED_ANSWER_TEMPLATE",
    "STREAMED_GROUNDED_TEMPLATE",
    "build_rag_prompt",
    "build_grounded_rag_prompt",
    "build_streamed_grounded_prompt",
    "parse_grounded_answer",
    "split_confidence_marker",
    "FAQ_GENERATION_TEMPLATE",
    "build_faq_generation_prompt",
    "parse_faq_response",
    "SUMMARY_CHAR_LIMIT",
    "SUMMARY_UPDATE_TEMPLATE",
    "build_summary_update_prompt",
    "clamp_summary",
]
