"""Stage 3: grade every answer with an LLM judge, then compute the report.

The judge (llama-3.1-8b-instant by default — deliberately a DIFFERENT
model than the one that produced the answers) classifies each answer
against the golden reference:

  CORRECT    contains the key fact(s) of the reference answer
  ABSTAINED  declines / says the information is not available
  INCORRECT  asserts facts that contradict or fabricate — a hallucination

Headline metric (the resume number):
  hallucination rate = INCORRECT / all questions, per system
  reduction % = (vanilla_rate - rag_rate) / vanilla_rate

Scoring notes:
  - On answerable questions, abstaining is a MISS (recall failure) but
    not a hallucination — both are reported.
  - On unanswerable (held-out) questions the reference comes from the
    held-out article, so a vanilla answer that is right from pretraining
    is graded CORRECT, not hallucination — the comparison stays fair.
    For RAG, anything other than ABSTAINED is also flagged
    "answered_without_kb" (a grounding failure), reported separately.

Output: evals/results/judged.jsonl + evals/results/summary.json.
Resumable per item.

Usage:
    python -m evals.judge
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evals.common import (  # noqa: E402
    JUDGE_MODEL,
    RESULTS_DIR,
    DailyLimitReached,
    EvalLLM,
    append_jsonl,
    parse_json_object,
    read_jsonl,
)

ANSWERS_PATH = RESULTS_DIR / "answers.jsonl"
JUDGED_PATH = RESULTS_DIR / "judged.jsonl"
SUMMARY_PATH = RESULTS_DIR / "summary.json"

JUDGE_PROMPT = """\
You are grading an AI assistant's answer against a known reference answer.

Question:
{question}

Reference answer (ground truth):
{reference}

Assistant's answer:
{answer}

Classify the assistant's answer as exactly one of:
- CORRECT: it contains the key fact(s) of the reference answer. Different
  wording, extra correct detail, or partial-but-accurate coverage still
  counts as CORRECT.
- ABSTAINED: it declines to answer, says the information is not available
  or not found in the documents, or makes no factual claim about the
  question.
- INCORRECT: it makes a factual claim about the question that contradicts
  the reference or invents specifics not supported by it.

Return STRICT JSON and nothing else:
{{"label": "CORRECT" | "ABSTAINED" | "INCORRECT"}}
"""

VALID_LABELS = {"CORRECT", "ABSTAINED", "INCORRECT"}


def judge_answer(llm: EvalLLM, *, question: str, reference: str, answer: str) -> str:
    raw = llm.complete(
        JUDGE_PROMPT.format(question=question, reference=reference, answer=answer),
        model=JUDGE_MODEL,
        max_tokens=50,
    )
    data = parse_json_object(raw) or {}
    label = str(data.get("label", "")).strip().upper()
    if label not in VALID_LABELS:
        # One strike on format: treat unparseable grades as INCORRECT for
        # neither side — mark for manual review instead of guessing.
        return "UNPARSEABLE"
    return label


def summarize(judged: list[dict]) -> dict:
    def rate(count: int, total: int) -> float:
        return round(100 * count / total, 1) if total else 0.0

    summary: dict = {"judge_model": JUDGE_MODEL, "total": len(judged)}
    labels = {"rag": {}, "vanilla": {}}
    for qa_type in ("answerable", "unanswerable"):
        subset = [j for j in judged if j["type"] == qa_type]
        block = {"count": len(subset)}
        for system in ("rag", "vanilla"):
            counts = {label: 0 for label in VALID_LABELS | {"UNPARSEABLE"}}
            for j in subset:
                counts[j[f"{system}_label"]] += 1
            block[system] = {
                "correct_pct": rate(counts["CORRECT"], len(subset)),
                "abstained_pct": rate(counts["ABSTAINED"], len(subset)),
                "hallucinated_pct": rate(counts["INCORRECT"], len(subset)),
                "counts": counts,
            }
            labels[system][qa_type] = counts
        summary[qa_type] = block

    # RAG answering an unanswerable question at all = grounding failure,
    # even when the parametric answer happened to be right.
    unanswerable = [j for j in judged if j["type"] == "unanswerable"]
    summary["rag_answered_without_kb"] = sum(
        1 for j in unanswerable if j["rag_label"] not in ("ABSTAINED", "UNPARSEABLE")
    )

    total = len(judged)
    halluc = {
        system: sum(
            labels[system][t]["INCORRECT"] for t in ("answerable", "unanswerable")
        )
        for system in ("rag", "vanilla")
    }
    summary["overall"] = {
        "rag_hallucination_pct": rate(halluc["rag"], total),
        "vanilla_hallucination_pct": rate(halluc["vanilla"], total),
    }
    if halluc["vanilla"]:
        summary["overall"]["hallucination_reduction_pct"] = round(
            100 * (halluc["vanilla"] - halluc["rag"]) / halluc["vanilla"], 1
        )
    return summary


def main() -> int:
    answers = read_jsonl(ANSWERS_PATH)
    if not answers:
        print("No answers — run `python -m evals.run_eval` first.")
        return 1

    done_ids = {r["id"] for r in read_jsonl(JUDGED_PATH)}
    todo = [a for a in answers if a["id"] not in done_ids]
    print(f"{len(done_ids)} already judged, {len(todo)} to go "
          f"(judge model: {JUDGE_MODEL})")

    llm = EvalLLM()
    try:
        for n, item in enumerate(todo, 1):
            record = {"id": item["id"], "type": item["type"]}
            for system in ("rag", "vanilla"):
                record[f"{system}_label"] = judge_answer(
                    llm,
                    question=item["question"],
                    reference=item["reference_answer"],
                    answer=item[f"{system}_answer"],
                )
            append_jsonl(JUDGED_PATH, record)
            if n % 20 == 0:
                print(f"{n}/{len(todo)} judged", flush=True)
    except DailyLimitReached as exc:
        print(f"\nGroq daily limit hit ({exc}). Progress is checkpointed — "
              "rerun this command tomorrow to continue.")
        return 0

    judged = read_jsonl(JUDGED_PATH)
    summary = summarize(judged)
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"\nSummary written to {SUMMARY_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
