"""Shared plumbing for the Phase 5 eval harness.

Model allocation (Groq free tier is the budget):
  - ANSWER_MODEL: the production chat model (settings default,
    llama-3.3-70b-versatile) — RAG and vanilla answers must come from the
    exact system being measured. Tightest daily token cap, so answer
    generation is the stage most likely to pause overnight.
  - GEN_MODEL / JUDGE_MODEL: llama-3.1-8b-instant — question generation
    and grading are cheap constrained tasks, the 8B tier has ~5x the
    daily budget, and judging with a DIFFERENT model than the one being
    graded avoids self-preference bias.

Every stage checkpoints to JSONL after each item: a daily-limit 429 exits
cleanly and the same command resumes tomorrow.
"""

import json
import os
import time
from pathlib import Path

import openai

REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = REPO_ROOT / "evals" / "results"
GOLDEN_PATH = REPO_ROOT / "evals" / "golden_qa.jsonl"
MANIFEST_PATH = REPO_ROOT / "evals" / "corpus_manifest.json"
HELDOUT_DIR = REPO_ROOT / "evals" / "heldout"

GEN_MODEL = os.environ.get("EVAL_GEN_MODEL", "llama-3.1-8b-instant")
JUDGE_MODEL = os.environ.get("EVAL_JUDGE_MODEL", "llama-3.1-8b-instant")
# None -> the production default from the app's provider factory.
ANSWER_MODEL = os.environ.get("EVAL_ANSWER_MODEL")

EVAL_USER_EMAIL = "eval-corpus@example.com"  # created by scripts/bulk_ingest.py

# A retry-after longer than this means a DAILY cap, not a per-minute one:
# sleeping through it inside a script makes no sense.
DAILY_LIMIT_THRESHOLD_SECONDS = 900


class DailyLimitReached(RuntimeError):
    """Groq daily quota exhausted — checkpoint and resume tomorrow."""


def get_answer_model() -> str:
    if ANSWER_MODEL:
        return ANSWER_MODEL
    from app.core.config import settings
    from app.infrastructure.llm.factory import _OPENAI_COMPATIBLE

    return settings.LLM_MODEL or _OPENAI_COMPATIBLE[settings.LLM_PROVIDER].model


class EvalLLM:
    """Direct Groq client with explicit 429 handling.

    SDK auto-retry is disabled: per-minute 429s are slept through using
    the server's retry-after, daily-cap 429s surface as DailyLimitReached
    so the calling stage can exit cleanly on its checkpoint.
    """

    def __init__(self):
        from app.core.config import settings

        if settings.LLM_PROVIDER != "groq":
            raise RuntimeError(
                "Eval harness expects LLM_PROVIDER=groq (budget logic is "
                f"Groq-specific); found {settings.LLM_PROVIDER!r}."
            )
        self.client = openai.OpenAI(
            api_key=settings.GROQ_API_KEY,
            base_url="https://api.groq.com/openai/v1",
            max_retries=0,
        )

    def complete(
        self,
        prompt: str,
        *,
        model: str,
        system: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 600,
    ) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        for attempt in range(8):
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                return response.choices[0].message.content or ""
            except openai.RateLimitError as exc:
                delay = _retry_after_seconds(exc) or 5 * 2**attempt
                if delay > DAILY_LIMIT_THRESHOLD_SECONDS:
                    raise DailyLimitReached(
                        f"retry-after {delay:.0f}s on {model}"
                    ) from exc
                print(f"  429 on {model}; sleeping {delay:.0f}s", flush=True)
                time.sleep(delay + 1)
            except (openai.APIConnectionError, openai.InternalServerError) as exc:
                delay = 5 * 2**attempt
                print(f"  {type(exc).__name__}; sleeping {delay}s", flush=True)
                time.sleep(delay)
        raise RuntimeError(f"LLM call failed after 8 attempts (model={model})")


def _retry_after_seconds(exc: openai.RateLimitError) -> float | None:
    try:
        value = exc.response.headers.get("retry-after")
        return float(value) if value else None
    except Exception:
        return None


def parse_json_object(raw: str) -> dict | None:
    """Parse a JSON object from model output, tolerating markdown fences
    and prose around the object. None if no valid object is found."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.lower().startswith("json"):
            text = text[4:]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def get_eval_user(db):
    from app.db.models.user import User

    user = db.query(User).filter(User.email == EVAL_USER_EMAIL).first()
    if user is None:
        raise RuntimeError(
            f"{EVAL_USER_EMAIL} not found — run scripts/bulk_ingest.py first."
        )
    return user
