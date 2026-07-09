from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, Index, Integer, ForeignKey, Text
from sqlalchemy.orm import relationship

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

    id = Column(Integer, primary_key=True, index=True)

    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)

    content = Column(Text, nullable=False)

    embedding = Column(Vector(384), nullable=False)

    organization = relationship("Organization")
    document = relationship("Document")
