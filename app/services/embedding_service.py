from typing import List
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db.models.document import Document
from app.db.models.embedding import DocumentEmbedding
from app.domain.embedding_service import EmbeddingService


def store_embeddings(
    db: Session,
    *,
    organization_id: int,
    document: Document,
    chunks: List[str],
    embedding_service: EmbeddingService,
):
    embeddings = embedding_service.embed_texts(chunks)

    records = [
        DocumentEmbedding(
            organization_id=organization_id,
            document_id=document.id,
            content=chunk,
            embedding=vector,
        )
        for chunk, vector in zip(chunks, embeddings)
    ]

    db.bulk_save_objects(records)
    db.commit()


def similarity_search(
    db: Session,
    *,
    organization_id: int,
    query_embedding: List[float],
    limit: int = 5,
):
    sql = text(
        """
        SELECT de.content, de.document_id, d.filename,
            (de.embedding <-> CAST(:query_embedding AS vector)) AS distance
        FROM document_embeddings de
        JOIN documents d ON d.id = de.document_id
        WHERE de.organization_id = :org_id
        ORDER BY de.embedding <-> CAST(:query_embedding AS vector)
        LIMIT :limit
        """
    )

    return db.execute(
        sql,
        {
            "org_id": organization_id,
            "query_embedding": query_embedding,
            "limit": limit,
        },
    ).fetchall()
