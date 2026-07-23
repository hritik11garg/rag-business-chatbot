from typing import List
from sqlalchemy.orm import Session
from sqlalchemy import bindparam, text

from app.core.config import settings
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


def store_generated_faq_embeddings(
    db: Session,
    *,
    organization_id: int,
    document_id: int,
    faqs: List[dict],
    embedding_service: EmbeddingService,
):
    """
    Store AI-generated FAQ embeddings derived from document chunks.
    """
    texts = [f"Q: {f['question']} A: {f['answer']}" for f in faqs]
    embeddings = embedding_service.embed_texts(texts)

    records = [
        DocumentEmbedding(
            organization_id=organization_id,
            document_id=document_id,
            content=text,
            embedding=vector,
        )
        for text, vector in zip(texts, embeddings)
    ]

    db.bulk_save_objects(records)
    db.commit()


def similarity_search(
    db: Session,
    *,
    organization_id: int,
    query_embedding: List[float],
    limit: int = settings.DEFAULT_TOP_K,
    document_ids: List[int] | None = None,
):
    # The org filter is unconditional — tenant isolation must hold no
    # matter what the caller passes. document_ids only narrows WITHIN
    # the org: another org's document id simply matches nothing.
    doc_filter = "AND de.document_id IN :doc_ids" if document_ids else ""

    sql = text(
        f"""
        SELECT de.content, de.document_id, d.filename,
            (de.embedding <-> CAST(:query_embedding AS vector)) AS distance
        FROM document_embeddings de
        JOIN documents d ON d.id = de.document_id
        WHERE de.organization_id = :org_id
        {doc_filter}
        ORDER BY de.embedding <-> CAST(:query_embedding AS vector)
        LIMIT :limit
        """
    )

    params = {
        "org_id": organization_id,
        "query_embedding": query_embedding,
        "limit": limit,
    }
    if document_ids:
        sql = sql.bindparams(bindparam("doc_ids", expanding=True))
        params["doc_ids"] = document_ids

    return db.execute(sql, params).fetchall()
