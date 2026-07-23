"""Retrieval-quality eval: Recall@k and MRR over the answerable golden set.

This measures the RETRIEVER in isolation (no LLM, no Groq budget): for each
answerable question, does the document the question was written from appear
in the top-k retrieved results, and at what rank?

It is also the headroom test for reranking. Reranking can only promote a
relevant document that dense retrieval already surfaced within the wider
candidate pool into the final top-k. So:

    reranking's ceiling  =  Recall@20 (candidate pool)  -  Recall@5 (final)

If that gap is ~0, reranking cannot help and we should not build it.

Usage:
    python -m evals.retrieval_eval                 # dense baseline
    python -m evals.retrieval_eval --rerank        # with cross-encoder
    python -m evals.retrieval_eval --candidates 30 # wider candidate pool
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.composition.singletons import get_embedding_service  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.services.embedding_service import similarity_search  # noqa: E402
from evals.common import (
    GOLDEN_PATH,
    RESULTS_DIR,
    get_eval_user,
    read_jsonl,
)  # noqa: E402

RECALL_KS = (1, 3, 5, 10, 20)


def _doc_rank(ranked_filenames: list[str], golden_source: str) -> int | None:
    """1-based rank of the first chunk belonging to the golden document,
    or None if it never appears. Document-level: repeated filenames from
    the same doc collapse to their best (earliest) position."""
    for i, filename in enumerate(ranked_filenames, start=1):
        if filename == golden_source:
            return i
    return None


def evaluate(*, candidates: int, use_rerank: bool) -> dict:
    golden = [g for g in read_jsonl(GOLDEN_PATH) if g["type"] == "answerable"]
    if not golden:
        raise SystemExit("No answerable golden questions found.")

    embedder = get_embedding_service()
    reranker = None
    if use_rerank:
        from app.infrastructure.rerank.cross_encoder import CrossEncoderReranker

        reranker = CrossEncoderReranker()

    db = SessionLocal()
    try:
        org_id = get_eval_user(db).organization_id
        ranks: list[int | None] = []

        for item in golden:
            question = item["question"]
            # Retrieve the wider candidate pool once.
            matches = similarity_search(
                db=db,
                organization_id=org_id,
                query_embedding=embedder.embed_query(question),
                limit=candidates,
            )
            if reranker is not None:
                order = reranker.rerank(
                    query=question,
                    passages=[m.content for m in matches],
                )
                matches = [matches[i] for i in order]
            # Rank is computed over the FULL (possibly reranked) pool, so
            # Recall@k is meaningful for every k up to `candidates`. Recall@5
            # is what the LLM actually sees; reranking's job is to lift a
            # relevant doc from deeper in the pool into that top-5.
            ranks.append(_doc_rank([m.filename for m in matches], item["source"]))

        total = len(ranks)
        recall = {
            k: sum(1 for r in ranks if r is not None and r <= k) / total
            for k in RECALL_KS
            if k <= candidates
        }
        mrr = sum((1.0 / r) for r in ranks if r is not None) / total
        found_in_pool = sum(1 for r in ranks if r is not None) / total

        return {
            "mode": "rerank" if use_rerank else "dense",
            "candidates": candidates,
            "questions": total,
            "recall_at_k": recall,
            "mrr": round(mrr, 4),
            "recall_in_candidate_pool": round(found_in_pool, 4),
        }
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=int, default=20)
    parser.add_argument("--rerank", action="store_true")
    args = parser.parse_args()

    result = evaluate(candidates=args.candidates, use_rerank=args.rerank)

    print(
        f"\nRetrieval eval — {result['mode']} "
        f"(pool={result['candidates']}, n={result['questions']})"
    )
    for k, v in result["recall_at_k"].items():
        print(f"  Recall@{k:<2} = {v:.1%}")
    print(f"  MRR       = {result['mrr']}")
    print(
        f"  in pool   = {result['recall_in_candidate_pool']:.1%} "
        f"(ceiling for any reranker)"
    )

    out = RESULTS_DIR / f"retrieval_{result['mode']}.json"
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    import json

    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"  saved -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
