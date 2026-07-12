from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class DocumentEmbedding(Base):
    __tablename__ = "document_embeddings"
    __table_args__ = (
        # Mirrors migration ff662c4e4bba so autogenerate sees it as expected
        Index(
            "ix_document_embeddings_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_l2_ops"},
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"), nullable=False
    )
    # Embeddings die with their document (migration 7446a24eef9e) —
    # the DB owns the cleanup rule, not whichever caller deletes.
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )

    content: Mapped[str] = mapped_column(Text, nullable=False)

    embedding = mapped_column(Vector(384), nullable=False)

    organization = relationship("Organization")
    document = relationship("Document")
