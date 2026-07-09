"""add hnsw index on document_embeddings

Revision ID: ff662c4e4bba
Revises: e13f88314368
Create Date: 2026-07-10 00:19:55.241312

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ff662c4e4bba'
down_revision: Union[str, Sequence[str], None] = 'e13f88314368'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # HNSW approximate-nearest-neighbor index (requires pgvector >= 0.5).
    # vector_l2_ops matches the <-> operator used in similarity_search;
    # embeddings are normalized, so L2 ordering equals cosine ordering.
    op.create_index(
        "ix_document_embeddings_embedding_hnsw",
        "document_embeddings",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_l2_ops"},
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_document_embeddings_embedding_hnsw",
        table_name="document_embeddings",
    )
