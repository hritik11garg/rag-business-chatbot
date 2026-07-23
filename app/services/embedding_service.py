import re
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
        SELECT de.id, de.content, de.document_id, d.filename,
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


def lexical_search(
    db: Session,
    *,
    organization_id: int,
    query_text: str,
    limit: int = settings.DEFAULT_TOP_K,
    document_ids: List[int] | None = None,
):
    """Keyword (full-text) arm of hybrid retrieval, org-scoped.

    The user query is reduced to alphanumeric lemmas and OR-joined into a
    tsquery, so a chunk ranks by how many query terms it contains (recall-
    friendly) rather than needing all of them. Building the tsquery from a
    strict [a-z0-9] allowlist makes it injection-safe: no user character
    can become a tsquery operator. Returns [] when the query has no usable
    terms. Matches ride the GIN index on content_tsv.
    """
    terms = re.findall(r"[a-z0-9]+", query_text.lower())
    if not terms:
        return []
    ts_query = " | ".join(terms)

    doc_filter = "AND de.document_id IN :doc_ids" if document_ids else ""
    sql = text(
        f"""
        SELECT de.id, de.content, de.document_id, d.filename,
            ts_rank_cd(de.content_tsv, to_tsquery('english', :ts_query)) AS rank
        FROM document_embeddings de
        JOIN documents d ON d.id = de.document_id
        WHERE de.organization_id = :org_id
          AND de.content_tsv @@ to_tsquery('english', :ts_query)
        {doc_filter}
        ORDER BY rank DESC
        LIMIT :limit
        """
    )
    params = {"org_id": organization_id, "ts_query": ts_query, "limit": limit}
    if document_ids:
        sql = sql.bindparams(bindparam("doc_ids", expanding=True))
        params["doc_ids"] = document_ids

    return db.execute(sql, params).fetchall()


def reciprocal_rank_fusion(*result_lists, k: int = 60, limit: int):
    """Fuse several ranked result lists into one by Reciprocal Rank Fusion.

    Each list contributes 1/(k + rank) to a row's score, so a chunk ranked
    highly by EITHER retriever floats up, and one ranked well by BOTH wins.
    RRF needs only the ranks, not the (incomparable) cosine-distance vs
    ts_rank scores. Rows are identified by chunk id (de.id), so the same
    chunk found by both arms is merged, not duplicated.
    """
    scores: dict[int, float] = {}
    rows_by_id: dict[int, object] = {}
    for results in result_lists:
        for rank, row in enumerate(results, start=1):
            scores[row.id] = scores.get(row.id, 0.0) + 1.0 / (k + rank)
            rows_by_id[row.id] = row
    ranked_ids = sorted(scores, key=lambda cid: scores[cid], reverse=True)
    return [rows_by_id[cid] for cid in ranked_ids[:limit]]
