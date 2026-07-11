# Evals — RAG vs. vanilla prompting

Measured evidence for the retrieval pipeline: a 100-question golden set
over a 500-PDF corpus, answered two ways by the **same model**
(`llama-3.3-70b-versatile`, the production chat model), graded by an
independent LLM judge (`llama-3.1-8b-instant`).

## Results (2026-07-11)

### Answerable questions (n=60) — the fact IS in the knowledge base

| system  | correct | abstained | hallucinated |
|---------|--------:|----------:|-------------:|
| RAG     | **86.7%** | 11.7% | 1.7% (1/60) |
| vanilla | 33.3%   | 63.3%     | 3.3% (2/60) |

RAG answers **2.6× more questions correctly** than the same model
without retrieval. Vanilla mostly abstains on these (obscure Wikipedia
subjects), which is the honest baseline behavior — the vanilla prompt
explicitly permits "I don't know".

### Unanswerable questions (n=40) — the fact is NOT in the knowledge base

| system  | correct (from pretraining) | abstained | hallucinated |
|---------|---------------------------:|----------:|-------------:|
| RAG     | 0%                         | **97.5%** | 2.5% (1/40) |
| vanilla | 32.5%                      | 62.5%     | 5.0% (2/40) |

RAG correctly says "not in the documents" on 39/40 out-of-scope
questions. Its one failure traces to a flawed golden question (u-011
references "the passage", so retrieval matched an unrelated document) —
kept in the results rather than cherry-picked out.

### Headline

| metric | RAG | vanilla |
|--------|----:|--------:|
| overall hallucination rate (n=100) | **2.0%** | 4.0% |

**Hallucination rate halved (50% reduction)** — note the small absolute
counts (2 vs 4 events); the answer-accuracy gap (86.7% vs 33.3%) and the
97.5% correct-abstention rate are the statistically stronger findings.

## Ingestion throughput

`scripts/bulk_ingest.py`, single process, local MiniLM (all-MiniLM-L6-v2)
on CPU, pgvector with HNSW:

| metric | value |
|--------|------:|
| documents ingested | 500 PDFs (Wikipedia articles, 4–20K chars) |
| chunks embedded + stored | 12,855 |
| wall time | 501.8 s |
| throughput | **59.8 docs/min · 25.6 chunks/sec** |
| failures | 0 |

## Method

1. **Corpus** (`scripts/fetch_wikipedia.py`): 550 random substantial
   Wikipedia articles (≥12KB wikitext, stubs/disambiguation rejected),
   each rendered to a real PDF. 500 are ingested (`evals/corpus/`);
   **50 are held out** (`evals/heldout/`) and never ingested.
   `corpus_manifest.json` records every article and its split.
2. **Ingest** (`scripts/bulk_ingest.py`): every corpus PDF runs through
   the production path (save → pypdf extract → normalize → 500-char
   chunks w/ 100 overlap → MiniLM embed → pgvector) under a dedicated
   eval organization. FAQ generation is disabled via the injected
   scheduler (`None`).
3. **Golden set** (`evals/generate_golden.py`): `llama-3.1-8b-instant`
   writes one self-contained factual Q&A per sampled passage —
   60 from ingested chunks (answerable), 40 from held-out articles
   (unanswerable relative to the KB). → `golden_qa.jsonl`
4. **Answers** (`evals/run_eval.py`): each question is answered by
   (a) **RAG**: top-5 pgvector retrieval + the app's own grounded
   prompt/parser (`app.prompts`), and (b) **vanilla**: same model, no
   context, told to say "I don't know" when unsure — both at the
   production temperature (0.1). → `results/answers.jsonl`
5. **Judge** (`evals/judge.py`): a *different* model grades each answer
   against the golden reference as CORRECT / ABSTAINED / INCORRECT
   (hallucination = INCORRECT). A vanilla answer that is right from
   pretraining counts as CORRECT — the comparison stays fair.
   → `results/judged.jsonl`, `results/summary.json`

Every stage checkpoints to JSONL after each item and resumes on rerun,
so Groq free-tier daily caps can interrupt any stage safely.

## Reproduce

```bash
python scripts/fetch_wikipedia.py --corpus 500 --heldout 50
python scripts/bulk_ingest.py
python -m evals.generate_golden --answerable 60 --unanswerable 40
python -m evals.run_eval
python -m evals.judge
```

Requires `LLM_PROVIDER=groq` in `.env` (the budget logic is
Groq-specific) and the docker-compose Postgres running. The corpus data
dirs are gitignored; the manifest, golden set, and results are committed.

## Limitations (read before quoting the numbers)

- **Small hallucination counts**: the 50% reduction is 2 events vs 4.
  Quote it together with the accuracy and abstention numbers.
- **Wikipedia is in the model's pretraining data**, which *helps the
  vanilla baseline* (it answers 33% of held-out questions from memory).
  On truly private business documents the gap would be larger, not
  smaller — this is the conservative direction.
- **LLM-generated golden set**: ~100 questions written by an 8B model;
  at least one (u-011) violates the self-containedness rule. Flaws were
  kept, not filtered.
- **8B judge**: grading is a constrained classification task, but an 8B
  judge still misgrades occasionally. Using a different model than the
  answerer avoids self-preference bias.
