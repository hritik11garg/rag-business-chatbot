"""Prompt for the rolling conversation-summary memory."""

# Hard cap applied AFTER the LLM responds — the prompt asks for brevity
# but the parser enforces it, so a rambling model can't grow the memory
# block unboundedly. ~1000 chars ≈ 250 tokens in the chat prompt.
SUMMARY_CHAR_LIMIT = 1000

SUMMARY_UPDATE_TEMPLATE = """
You maintain a compact memory of important facts from a user's support
conversation with a document-based assistant.

Current memory (may be empty):
{current_summary}

Recent conversation:
{transcript}

Rewrite the memory, merging in any NEW important facts from the recent
conversation. Rules:
- Keep only durable facts worth remembering: the user's goals,
  preferences, and key answers already given to them
- Drop greetings, chit-chat, repetition, and anything already covered
- At most 8 short lines, plain text only
- If there is nothing worth remembering, output the current memory
  unchanged (or nothing if it was empty)
- Output ONLY the memory text, no headers or commentary
"""


def build_summary_update_prompt(*, current_summary: str, transcript: str) -> str:
    return SUMMARY_UPDATE_TEMPLATE.format(
        current_summary=current_summary or "(empty)",
        transcript=transcript,
    )


def clamp_summary(raw: str) -> str:
    return raw.strip()[:SUMMARY_CHAR_LIMIT]
