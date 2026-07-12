"""Create the bench users the Locust scenario logs in as.

50 concurrent simulated users sharing ONE account would serialize on a
single user's chat history and summary row — unrealistic contention.
Instead each Locust user gets its own account, all inside the eval
corpus organization (eval-corpus-org, 500 docs / 12,855 chunks from
Phase 5), so every /chat request retrieves against a real-sized index.

Idempotent: existing bench users are left untouched.

Usage:
    python benchmarks/seed_users.py            # creates 50
    python benchmarks/seed_users.py --count 20
"""

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from app.core.security import hash_password  # noqa: E402
from app.db.models.organization import Organization  # noqa: E402
from app.db.models.user import User  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402

EVAL_ORG_NAME = "eval-corpus-org"
BENCH_EMAIL_TEMPLATE = "bench-{i:03d}@example.com"
BENCH_PASSWORD = "bench-password"  # dev-only accounts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=50)
    args = parser.parse_args()

    db = SessionLocal()
    try:
        org = db.query(Organization).filter(Organization.name == EVAL_ORG_NAME).first()
        if org is None:
            print(
                f"Organization '{EVAL_ORG_NAME}' not found — run "
                "scripts/bulk_ingest.py first (the bench needs its corpus)."
            )
            return 1

        existing = {
            row.email
            for row in db.query(User.email).filter(User.organization_id == org.id).all()
        }
        hashed = hash_password(BENCH_PASSWORD)  # bcrypt once, not 50 times
        created = 0
        for i in range(1, args.count + 1):
            email = BENCH_EMAIL_TEMPLATE.format(i=i)
            if email in existing:
                continue
            db.add(
                User(
                    email=email,
                    hashed_password=hashed,
                    is_admin=False,
                    organization_id=org.id,
                )
            )
            created += 1
        db.commit()
        print(
            f"org id={org.id}: {created} bench users created, "
            f"{args.count - created} already existed"
        )
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
