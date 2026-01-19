from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, Integer, ForeignKey, Text
from sqlalchemy.orm import relationship

from app.db.base import Base


class DocumentEmbedding(Base):
    __tablename__ = "document_embeddings"

    id = Column(Integer, primary_key=True, index=True)

    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)

    content = Column(Text, nullable=False)

    embedding = Column(Vector(384), nullable=False)

    organization = relationship("Organization")
    document = relationship("Document")
