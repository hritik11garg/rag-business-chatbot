"""Bulk-ingest the eval corpus through the real ingestion pipeline.

Runs every PDF in evals/corpus/ through UploadDocumentUseCase.ingest_pdf —
the same save→extract→normalize→chunk→embed→pgvector path production uses —
under a dedicated eval organization, with FAQ generation disabled (the
scheduler is injected as None; 500 docs must not enqueue 500 LLM jobs).

Resumable: PDFs whose filename already exists as a document in the eval org
are skipped, so a crashed run continues where it stopped.

Throughput (docs/min, chunks/sec) is printed and written to
evals/ingest_stats.json for evals/README.md.

Usage:
    python scripts/bulk_ingest.py
"""

import json
import shutil
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from app.core.security import hash_password  # noqa: E402
from app.composition.singletons import get_embedding_service  # noqa: E402
from app.db.models.document import Document  # noqa: E402
from app.db.models.organization import Organization  # noqa: E402
from app.db.models.user import User  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.use_cases.upload_document import (  # noqa: E402
    UPLOAD_BASE_DIR,
    PdfIngestError,
    UploadDocumentUseCase,
)

CORPUS_DIR = REPO_ROOT / "evals" / "corpus"
STATS_PATH = REPO_ROOT / "evals" / "ingest_stats.json"

EVAL_ORG_NAME = "eval-corpus-org"
EVAL_USER_EMAIL = "eval-corpus@example.com"
EVAL_USER_PASSWORD = "eval-corpus-password"  # dev-only account


def get_or_create_eval_user(db) -> User:
    user = db.query(User).filter(User.email == EVAL_USER_EMAIL).first()
    if user:
        return user
    org = Organization(name=EVAL_ORG_NAME)
    db.add(org)
    db.flush()
    user = User(
        email=EVAL_USER_EMAIL,
        hashed_password=hash_password(EVAL_USER_PASSWORD),
        is_admin=True,
        organization_id=org.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def main() -> int:
    pdfs = sorted(CORPUS_DIR.glob("*.pdf"))
    if not pdfs:
        print(f"No PDFs in {CORPUS_DIR} — run scripts/fetch_wikipedia.py first.")
        return 1

    db = SessionLocal()
    try:
        user = get_or_create_eval_user(db)
        org_id = user.organization_id
        print(f"Eval org id={org_id}, user id={user.id}, {len(pdfs)} PDFs found")

        already = {
            row.filename
            for row in db.query(Document.filename)
            .filter(Document.organization_id == org_id)
            .all()
        }
        todo = [p for p in pdfs if p.name not in already]
        print(f"{len(already)} already ingested, {len(todo)} to go")
        if not todo:
            return 0

        print("Warming embedding model...")
        embedding_service = get_embedding_service()

        use_case = UploadDocumentUseCase(
            db,
            embedding_service=embedding_service,
            schedule_faq_generation=None,  # bulk mode: no FAQ jobs
        )

        org_dir = Path(UPLOAD_BASE_DIR) / f"org_{org_id}"
        org_dir.mkdir(parents=True, exist_ok=True)

        docs_done = 0
        chunks_done = 0
        failures: list[str] = []
        started = time.perf_counter()

        for pdf in todo:
            target = org_dir / pdf.name
            shutil.copyfile(pdf, target)  # pipeline owns (and may delete) the copy
            try:
                result = use_case.ingest_pdf(
                    file_path=str(target),
                    organization_id=org_id,
                    uploaded_by=user.id,
                )
            except PdfIngestError as exc:
                failures.append(f"{pdf.name}: {exc}")
                continue
            docs_done += 1
            chunks_done += result["chunks_stored"]
            if docs_done % 50 == 0:
                elapsed = time.perf_counter() - started
                print(
                    f"{docs_done}/{len(todo)} docs, {chunks_done} chunks, "
                    f"{docs_done / (elapsed / 60):.1f} docs/min",
                    flush=True,
                )

        elapsed = time.perf_counter() - started
        stats = {
            "documents_ingested": docs_done,
            "chunks_stored": chunks_done,
            "elapsed_seconds": round(elapsed, 1),
            "docs_per_minute": round(docs_done / (elapsed / 60), 1),
            "chunks_per_second": round(chunks_done / elapsed, 1),
            "failures": failures,
            "previously_ingested": len(already),
        }
        STATS_PATH.write_text(json.dumps(stats, indent=2), encoding="utf-8")
        print(json.dumps(stats, indent=2))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
