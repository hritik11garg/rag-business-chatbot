"""cascade delete embeddings with parent document

Deleting a document used to require a hand-written raw-SQL DELETE of
its embeddings in the use case — schema knowledge living in Python.
With ON DELETE CASCADE the database owns that rule (single source of
truth) and the cleanup cannot be forgotten by any future caller.

Revision ID: 7446a24eef9e
Revises: 636d779e3f1a
Create Date: 2026-07-13 00:05:28.823391

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7446a24eef9e"
down_revision: Union[str, Sequence[str], None] = "636d779e3f1a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FK_NAME = "document_embeddings_document_id_fkey"
TABLE = "document_embeddings"


def upgrade() -> None:
    op.drop_constraint(FK_NAME, TABLE, type_="foreignkey")
    op.create_foreign_key(
        FK_NAME,
        TABLE,
        "documents",
        ["document_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(FK_NAME, TABLE, type_="foreignkey")
    op.create_foreign_key(
        FK_NAME,
        TABLE,
        "documents",
        ["document_id"],
        ["id"],
    )
