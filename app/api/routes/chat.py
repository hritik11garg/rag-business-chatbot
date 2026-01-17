from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.services.llm_service import generate_answer
from app.api.deps import get_db, get_current_user
from app.db.models.user import User
from app.services.embedding_service import (
    embed_query,
    similarity_search,
)


router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("")
def chat(
    question: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Answer a user question using organization-specific knowledge base.
    """

    # Step 1: Embed rewritten query
    query_embedding = embed_query(question)

    # Step 2: Retrieve relevant chunks
    matches = similarity_search(
        db=db,
        organization_id=current_user.organization_id,
        query_embedding=query_embedding,
        limit=5,
    )

    # ✅ Step 3: Always check empty first
    if not matches:
        return {
            "question": question,
            "answer": "No relevant information found in the knowledge base.",
            "confidence": "low",
        }


    # Step 4: Build context from retrieved chunks
    context = "\n\n".join([row.content for row in matches])

    # Step 5: Generate final grounded answer
    answer = generate_answer(
        question=question,
        context=context,
    )

    return {
        "question": question,
        "answer": answer,
    }
