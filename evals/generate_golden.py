"""Stage 1: build the golden Q&A set (default 60 answerable + 40 unanswerable).

  - Answerable questions are generated from randomly sampled chunks of
    documents that WERE ingested — the correct behavior is to answer.
  - Unanswerable questions are generated from held-out articles of the
    same distribution that were NEVER ingested — relative to the
    knowledge base the correct behavior is to abstain. (The vanilla
    baseline may still know the answer from pretraining; the judge
    grades it against the held-out reference, so that counts as
    CORRECT, not hallucination — the comparison stays fair.)

Questions must be self-contained (the subject named explicitly) so they
are meaningful both with retrieval and without it.

Output: evals/golden_qa.jsonl (committed). Resumable per item.

Usage:
    python -m evals.generate_golden [--answerable 60] [--unanswerable 40]
"""

import argparse
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.db.session import SessionLocal  # noqa: E402
from evals.common import (  # noqa: E402
    GEN_MODEL,
    GOLDEN_PATH,
    HELDOUT_DIR,
    DailyLimitReached,
    EvalLLM,
    append_jsonl,
    get_eval_user,
    parse_json_object,
    read_jsonl,
)

QUESTION_PROMPT = """\
You will be given a passage from a reference document.

Write ONE factual question that can be answered using ONLY this passage,
plus the correct answer.

Rules:
- The question must be fully self-contained: name the subject explicitly.
  Never write "this article", "he", "she", "it", or "the passage".
- Ask about one specific fact: a date, number, name, place, or cause.
- The answer must be short (one sentence at most) and stated in the passage.

Return STRICT JSON and nothing else:
{"question": "<question>", "answer": "<answer>"}

Passage:
"""

MIN_CHUNK_CHARS = 350
PASSAGE_CHARS = 1500


def sample_corpus_passages(db, org_id: int, count: int, rng) -> list[dict]:
    """One random substantial chunk from each of `count` random documents."""
    rows = db.execute(
        text(
            """
            SELECT DISTINCT ON (de.document_id) de.document_id, d.filename,
                   de.content
            FROM document_embeddings de
            JOIN documents d ON d.id = de.document_id
            WHERE de.organization_id = :org_id
              AND length(de.content) >= :min_chars
            ORDER BY de.document_id, random()
            """
        ),
        {"org_id": org_id, "min_chars": MIN_CHUNK_CHARS},
    ).fetchall()
    rng.shuffle(rows := list(rows))
    return [{"source": r.filename, "passage": r.content} for r in rows[:count]]


def sample_heldout_passages(count: int, rng) -> list[dict]:
    """A mid-article slice from each of `count` random held-out articles."""
    files = sorted(HELDOUT_DIR.glob("*.txt"))
    if len(files) < count:
        raise RuntimeError(
            f"Only {len(files)} held-out articles; need {count}. "
            "Run scripts/fetch_wikipedia.py."
        )
    passages = []
    for path in rng.sample(files, count):
        full = path.read_text(encoding="utf-8")
        start = min(len(full) // 3, max(0, len(full) - PASSAGE_CHARS))
        passages.append(
            {"source": path.name, "passage": full[start : start + PASSAGE_CHARS]}
        )
    return passages


def generate_item(llm: EvalLLM, passage: str) -> dict | None:
    data = parse_json_object(
        llm.complete(QUESTION_PROMPT + passage, model=GEN_MODEL, max_tokens=300)
    )
    if not data:
        return None
    question = str(data.get("question", "")).strip()
    answer = str(data.get("answer", "")).strip()
    if not question or not answer or len(question) > 300:
        return None
    return {"question": question, "answer": answer}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--answerable", type=int, default=60)
    parser.add_argument("--unanswerable", type=int, default=40)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    existing = read_jsonl(GOLDEN_PATH)
    have = {"answerable": 0, "unanswerable": 0}
    seen_sources = set()
    seen_questions = set()
    for item in existing:
        have[item["type"]] += 1
        seen_sources.add(item["source"])
        seen_questions.add(item["question"].lower())
    if existing:
        print(
            f"Resuming: {have['answerable']} answerable, "
            f"{have['unanswerable']} unanswerable already present"
        )

    llm = EvalLLM()
    db = SessionLocal()
    try:
        org_id = get_eval_user(db).organization_id

        plan = [
            (
                "answerable",
                [
                    p
                    for p in sample_corpus_passages(
                        db, org_id, args.answerable + 30, rng
                    )
                    if p["source"] not in seen_sources
                ],
                args.answerable,
            ),
            (
                "unanswerable",
                [
                    p
                    for p in sample_heldout_passages(
                        min(
                            args.unanswerable + 10, len(list(HELDOUT_DIR.glob("*.txt")))
                        ),
                        rng,
                    )
                    if p["source"] not in seen_sources
                ],
                args.unanswerable,
            ),
        ]

        for qa_type, passages, target in plan:
            for passage in passages:
                if have[qa_type] >= target:
                    break
                item = generate_item(llm, passage["passage"])
                if item is None or item["question"].lower() in seen_questions:
                    continue
                have[qa_type] += 1
                seen_questions.add(item["question"].lower())
                record = {
                    "id": f"{qa_type[0]}-{have[qa_type]:03d}",
                    "type": qa_type,
                    "question": item["question"],
                    "reference_answer": item["answer"],
                    "source": passage["source"],
                }
                append_jsonl(GOLDEN_PATH, record)
                if have[qa_type] % 10 == 0:
                    print(f"{qa_type}: {have[qa_type]}/{target}", flush=True)
            if have[qa_type] < target:
                print(
                    f"WARNING: only {have[qa_type]}/{target} {qa_type} items "
                    "generated (ran out of usable passages) — rerun to top up."
                )

        print(
            f"Golden set: {have['answerable']} answerable + "
            f"{have['unanswerable']} unanswerable at {GOLDEN_PATH}"
        )
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
