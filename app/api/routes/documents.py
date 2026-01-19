import os
from typing import List

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.db.models.document import Document
from app.db.models.user import User
from app.services.document_processing import (
    extract_text_from_pdf,
    normalize_text,
    chunk_text,
)
from app.services.embedding_service import store_embeddings
# Celery task (real background worker)
from app.tasks.faq_tasks import generate_faqs_task

router = APIRouter(prefix="/documents", tags=["documents"])

UPLOAD_BASE_DIR = "uploads"


# =========================================================
# 📄 List organization documents
# =========================================================
@router.get("", response_model=List[dict])
def list_documents(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    documents = (
        db.query(Document)
        .filter(Document.organization_id == current_user.organization_id)
        .order_by(Document.id.desc())
        .all()
    )

    return [
        {
            "id": doc.id,
            "filename": doc.filename,
            "content_type": doc.content_type,
            "uploaded_by": doc.uploaded_by,
            "created_at": doc.created_at,
            "updated_at": doc.updated_at,
        }
        for doc in documents
    ]


# =========================================================
# 📤 Upload document + RAG ingestion
# =========================================================
@router.post("/upload", status_code=201)
def upload_document(
        file: UploadFile = File(...),
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    if file.content_type != "application/pdf":
        raise HTTPException(400, "Only PDF files are supported")

    # Org isolation folder
    org_dir = os.path.join(UPLOAD_BASE_DIR, f"org_{current_user.organization_id}")
    os.makedirs(org_dir, exist_ok=True)

    # Filename versioning
    name, ext = os.path.splitext(file.filename)
    file_path = os.path.join(org_dir, file.filename)
    counter = 1

    while os.path.exists(file_path):
        counter += 1
        file_path = os.path.join(org_dir, f"{name}_v{counter}{ext}")

    final_filename = os.path.basename(file_path)
    file.file.seek(0)

    # Save file
    with open(file_path, "wb") as f:
        f.write(file.file.read())

    # Validate & extract
    try:
        raw_text = extract_text_from_pdf(file_path)
        clean_text = normalize_text(raw_text)
        chunks = chunk_text(clean_text)
    except Exception:
        os.remove(file_path)
        raise HTTPException(400, "Corrupted or unreadable PDF")

    if not chunks:
        os.remove(file_path)
        raise HTTPException(400, "No readable content found")

    # Store document metadata
    document = Document(
        filename=final_filename,
        content_type=file.content_type,
        organization_id=current_user.organization_id,
        uploaded_by=current_user.id,
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    # Store embeddings
    try:
        store_embeddings(
            db=db,
            organization_id=current_user.organization_id,
            document=document,
            chunks=chunks,
        )
    except Exception:
        db.delete(document)
        db.commit()
        os.remove(file_path)
        raise HTTPException(500, "Embedding generation failed")

    # 🚀 Send FAQs to Celery worker (ONLY once)
    generate_faqs_task.delay(chunks, document.id, current_user.organization_id)

    return {
        "id": document.id,
        "filename": document.filename,
        "organization_id": document.organization_id,
        "chunks_stored": len(chunks),
    }


# =========================================================
# 🗑 Delete document + vector cleanup
# =========================================================
@router.delete("/{document_id}", status_code=200)
def delete_document(document_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    document = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.organization_id == current_user.organization_id,
        )
        .first()
    )

    if not document:
        raise HTTPException(404, "Document not found")

    # Remove embeddings
    db.execute(
        text("DELETE FROM document_embeddings WHERE document_id = :doc_id"),
        {"doc_id": document_id},
    )

    # Remove file
    file_path = os.path.join("uploads", f"org_{current_user.organization_id}", document.filename)
    if os.path.exists(file_path):
        os.remove(file_path)

    db.delete(document)
    db.commit()

    return {"message": "Document and embeddings deleted successfully"}
