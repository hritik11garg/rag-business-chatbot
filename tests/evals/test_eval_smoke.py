"""Smoke tests for the eval harness plumbing (no LLM calls).

Guards the pure logic the Phase 5 results depend on: tolerant JSON
parsing of model output, and the metric arithmetic in judge.summarize.
"""

from evals.common import parse_json_object
from evals.judge import summarize


def test_parse_json_object_plain():
    assert parse_json_object('{"label": "CORRECT"}') == {"label": "CORRECT"}


def test_parse_json_object_fenced():
    raw = '```json\n{"question": "Q?", "answer": "A"}\n```'
    assert parse_json_object(raw) == {"question": "Q?", "answer": "A"}


def test_parse_json_object_with_prose():
    raw = 'Sure! Here is the JSON:\n{"label": "ABSTAINED"} Hope that helps.'
    assert parse_json_object(raw) == {"label": "ABSTAINED"}


def test_parse_json_object_garbage_is_none():
    assert parse_json_object("no json here") is None
    assert parse_json_object("{broken json]") is None


def judged_row(qa_type, rag, vanilla):
    return {"type": qa_type, "rag_label": rag, "vanilla_label": vanilla}


def test_summarize_computes_rates_and_reduction():
    judged = [
        judged_row("answerable", "CORRECT", "INCORRECT"),
        judged_row("answerable", "CORRECT", "ABSTAINED"),
        judged_row("answerable", "ABSTAINED", "CORRECT"),
        judged_row("answerable", "INCORRECT", "INCORRECT"),
        judged_row("unanswerable", "ABSTAINED", "INCORRECT"),
        judged_row("unanswerable", "ABSTAINED", "ABSTAINED"),
        judged_row("unanswerable", "CORRECT", "CORRECT"),
        judged_row("unanswerable", "ABSTAINED", "INCORRECT"),
    ]

    summary = summarize(judged)

    assert summary["total"] == 8
    assert summary["answerable"]["rag"]["correct_pct"] == 50.0
    assert summary["answerable"]["rag"]["hallucinated_pct"] == 25.0
    assert summary["unanswerable"]["rag"]["abstained_pct"] == 75.0
    # RAG answered 1 of 4 unanswerable questions => grounding failure
    assert summary["rag_answered_without_kb"] == 1
    # hallucinations: rag 1/8, vanilla 4/8 => 75% reduction
    assert summary["overall"]["rag_hallucination_pct"] == 12.5
    assert summary["overall"]["vanilla_hallucination_pct"] == 50.0
    assert summary["overall"]["hallucination_reduction_pct"] == 75.0


def test_summarize_handles_empty_subsets():
    judged = [judged_row("answerable", "CORRECT", "CORRECT")]
    summary = summarize(judged)
    assert summary["unanswerable"]["count"] == 0
    assert summary["unanswerable"]["rag"]["correct_pct"] == 0.0
    assert "hallucination_reduction_pct" not in summary["overall"]
