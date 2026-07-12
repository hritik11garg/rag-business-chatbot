"""Stage 2: answer every golden question two ways on the SAME model.

  RAG     — the production path: embed the question, top-5 pgvector
            retrieval inside the eval org, the app's own grounded
            prompt + parser (app.prompts), production temperature.
  Vanilla — the same model, same question, no retrieved context: the
            baseline the resume claim compares against.

Both use the production answer model (llama-3.3-70b-versatile by
default), which has the tightest Groq daily token budget (~100K/day vs
~500K for the 8B tier) — expect roughly 1.2K tokens per question, so
~100 questions fits in about one day's budget. On a daily-limit 429 the
run exits cleanly; rerun the same command to resume from the checkpoint.

Output: evals/results/answers.jsonl. Resumable per item.

Usage:
    python -m evals.run_eval
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.composition.singletons import get_embedding_service  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.prompts import build_grounded_rag_prompt, parse_grounded_answer  # noqa: E402
from app.prompts.rag import SYSTEM_PROMPT  # noqa: E402
from app.services.embedding_service import similarity_search  # noqa: E402
from evals.common import (  # noqa: E402
    GOLDEN_PATH,
    RESULTS_DIR,
    DailyLimitReached,
    EvalLLM,
    append_jsonl,
    get_answer_model,
    get_eval_user,
    read_jsonl,
)

ANSWERS_PATH = RESULTS_DIR / "answers.jsonl"

VANILLA_SYSTEM = "You are a helpful assistant. Answer factual questions concisely."
VANILLA_TEMPLATE = """\
Answer the following question in one or two sentences. If you do not
know the answer, say so plainly.

Question:
{question}
"""

TOP_K = 5  # production default (ChatRequest.top_k)
PACE_SECONDS = 2  # stay under the 70B per-minute token cap most of the time


def main() -> int:
    golden = read_jsonl(GOLDEN_PATH)
    if not golden:
        print("No golden set — run `python -m evals.generate_golden` first.")
        return 1

    done_ids = {r["id"] for r in read_jsonl(ANSWERS_PATH)}
    todo = [g for g in golden if g["id"] not in done_ids]
    print(f"{len(done_ids)} already answered, {len(todo)} to go")
    if not todo:
        return 0

    model = get_answer_model()
    temperature = settings.LLM_TEMPERATURE
    print(f"Answer model: {model} (temperature={temperature})")

    llm = EvalLLM()
    embedder = get_embedding_service()
    db = SessionLocal()
    try:
        org_id = get_eval_user(db).organization_id

        started = time.monotonic()
        for n, item in enumerate(todo, 1):
            question = item["question"]

            matches = similarity_search(
                db=db,
                organization_id=org_id,
                query_embedding=embedder.embed_query(question),
                limit=TOP_K,
            )
            context = "\n\n".join(row.content for row in matches)
            grounded = parse_grounded_answer(
                llm.complete(
                    build_grounded_rag_prompt(question=question, context=context),
                    model=model,
                    system=SYSTEM_PROMPT,
                    temperature=temperature,
                    max_tokens=400,
                )
            )

            vanilla_answer = llm.complete(
                VANILLA_TEMPLATE.format(question=question),
                model=model,
                system=VANILLA_SYSTEM,
                temperature=temperature,
                max_tokens=400,
            ).strip()

            append_jsonl(
                ANSWERS_PATH,
                {
                    "id": item["id"],
                    "type": item["type"],
                    "question": question,
                    "reference_answer": item["reference_answer"],
                    "golden_source": item["source"],
                    "rag_answer": grounded.answer,
                    "rag_confidence": grounded.confidence,
                    "rag_sources": sorted({row.filename for row in matches}),
                    "vanilla_answer": vanilla_answer,
                },
            )
            if n % 10 == 0:
                rate = n / ((time.monotonic() - started) / 60)
                print(f"{n}/{len(todo)} answered ({rate:.1f} q/min)", flush=True)
            time.sleep(PACE_SECONDS)

        print(f"All answers at {ANSWERS_PATH}")
        return 0
    except DailyLimitReached as exc:
        print(
            f"\nGroq daily limit hit ({exc}). Progress is checkpointed — "
            "rerun this command tomorrow to continue."
        )
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
