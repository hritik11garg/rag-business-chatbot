from typing import List

from sentence_transformers import SentenceTransformer
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.models.document import Document
from app.db.models.embedding import DocumentEmbedding

# Load model once (IMPORTANT: do NOT reload per request)
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")


def generate_embeddings(chunks: List[str]) -> List[List[float]]:
    """
    Generate vector embeddings for a list of text chunks.
    """
    return embedding_model.encode(
        chunks,
        convert_to_numpy=True,
        normalize_embeddings=True
    ).tolist()


def store_embeddings(
        db: Session,
        *,
        organization_id: int,
        document: Document,
        chunks: List[str],
):
    """
    Generate embeddings and store them in the database.
    """

    embeddings = generate_embeddings(chunks)

    records = []
    for chunk_text, vector in zip(chunks, embeddings):
        records.append(
            DocumentEmbedding(
                organization_id=organization_id,
                document_id=document.id,
                content=chunk_text,
                embedding=vector,
            )
        )

    db.bulk_save_objects(records)
    db.commit()


def similarity_search(
        db: Session,
        *,
        organization_id: int,
        query_embedding: list[float],
        limit: int = 5,
):
    """
    Perform vector similarity search using pgvector.
    Returns top matching document chunks.
    """

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

    results = db.execute(
        sql,
        {
            "org_id": organization_id,
            "query_embedding": query_embedding,
            "limit": limit,
        },
    ).fetchall()

    return results


def embed_query(text: str) -> list[float]:
    """
    Generate embedding for a user query.
    """
    return embedding_model.encode(
        text,
        convert_to_numpy=True,
        normalize_embeddings=True,
    ).tolist()


def store_generated_faq_embeddings(
        db,
        *,
        organization_id: int,
        document_id: int,
        faqs: list[dict],
):
    """
    Store AI-generated FAQ embeddings derived from document chunks.
    """

    texts = [f"Q: {f['question']} A: {f['answer']}" for f in faqs]
    vectors = generate_embeddings(texts)

    for text, vector in zip(texts, vectors):
        db.add(
            DocumentEmbedding(
                organization_id=organization_id,
                document_id=document_id,
                content=text,
                embedding=vector,
            )
        )

    db.commit()
