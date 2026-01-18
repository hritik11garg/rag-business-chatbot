import os
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.api.deps import get_db, get_current_user
from app.db.models.document import Document
from app.db.models.user import User
from app.services.embedding_service import store_embeddings, store_generated_faq_embeddings
from app.services.document_processing import (
    extract_text_from_pdf,
    normalize_text,
    chunk_text,
)
from app.services.faq_generator import generate_and_store_faqs


router = APIRouter(prefix="/documents", tags=["documents"])

# Base folder where all organization documents will be stored
UPLOAD_BASE_DIR = "uploads"


@router.post("/upload", status_code=201)
def upload_document(
    background_tasks: BackgroundTasks,              # Used to run heavy AI tasks after response
    file: UploadFile = File(...),                   # Incoming PDF file
    db: Session = Depends(get_db),                  # Database session
    current_user: User = Depends(get_current_user), # Authenticated user
):
    """
    Upload a document for the current user's organization.

    Enterprise Flow:
    1. Validate file type
    2. Version-safe storage
    3. PDF validation
    4. Create DB document record
    5. Generate embeddings (RAG ingestion)
    6. Background FAQ generation
    """

    # ---------------------------------------------------------
    # 1️⃣ Validate content type to allow only PDFs
    # ---------------------------------------------------------
    if file.content_type not in {"application/pdf"}:
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported",
        )

    # ---------------------------------------------------------
    # 2️⃣ Create organization-specific folder for isolation
    # Each org gets its own directory:
    # uploads/org_1/, uploads/org_2/, etc.
    # ---------------------------------------------------------
    org_dir = os.path.join(UPLOAD_BASE_DIR, f"org_{current_user.organization_id}")
    os.makedirs(org_dir, exist_ok=True)

    # ---------------------------------------------------------
    # 3️⃣ Enterprise filename versioning
    # Prevents overwriting files with same name
    # Example:
    # policy.pdf → policy_v2.pdf → policy_v3.pdf
    # ---------------------------------------------------------
    original_name = file.filename
    name, ext = os.path.splitext(original_name)

    counter = 1
    file_path = os.path.join(org_dir, original_name)

    while os.path.exists(file_path):
        counter += 1
        file_path = os.path.join(org_dir, f"{name}_v{counter}{ext}")

    final_filename = os.path.basename(file_path)

    # Reset pointer in case FastAPI pre-read part of the stream
    file.file.seek(0)

    # ---------------------------------------------------------
    # 4️⃣ Save PDF safely to disk
    # ---------------------------------------------------------
    try:
        with open(file_path, "wb") as f:
            f.write(file.file.read())
    except Exception:
        raise HTTPException(500, "Failed to save uploaded file")

    # ---------------------------------------------------------
    # 5️⃣ Validate PDF integrity before storing in DB
    # Prevents corrupt PDFs entering pipeline
    # ---------------------------------------------------------
    try:
        raw_text = extract_text_from_pdf(file_path)
        clean_text = normalize_text(raw_text)
        chunks = chunk_text(clean_text)
    except Exception:
        # Remove invalid file immediately
        os.remove(file_path)
        raise HTTPException(400, "Uploaded PDF is corrupted or unreadable")

    # Ensure PDF contains readable content
    if not chunks:
        os.remove(file_path)
        raise HTTPException(400, "No readable text found in the document")

    # ---------------------------------------------------------
    # 6️⃣ Create Document record ONLY after validation
    # Ensures DB is always clean & consistent
    # ---------------------------------------------------------
    document = Document(
        filename=final_filename,
        content_type=file.content_type,
        organization_id=current_user.organization_id,
        uploaded_by=current_user.id,
    )

    db.add(document)
    db.commit()
    db.refresh(document)

    # ---------------------------------------------------------
    # 7️⃣ Generate embeddings for each chunk and store in pgvector
    # If this fails → rollback document + remove file
    # Prevents orphaned records
    # ---------------------------------------------------------
    try:
        store_embeddings(
            db=db,
            organization_id=current_user.organization_id,
            document=document,
            chunks=chunks,
        )
    except Exception as e:
        db.delete(document)
        db.commit()
        os.remove(file_path)
        raise HTTPException(500, f"Failed to generate embeddings: {str(e)}")

    # ---------------------------------------------------------
    # 8️⃣ Background AI task: Generate FAQs from document chunks
    # This runs AFTER response so upload remains fast
    # ---------------------------------------------------------
    background_tasks.add_task(
        generate_and_store_faqs,
        chunks,
        document.id,
        current_user.organization_id,
    )

    # ---------------------------------------------------------
    # 9️⃣ Final Response
    # ---------------------------------------------------------
    return {
        "id": document.id,
        "filename": document.filename,
        "organization_id": document.organization_id,
        "chunks_stored": len(chunks),
    }



@router.delete("/{document_id}", status_code=200)
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a document and all associated embeddings (enterprise cleanup).
    """

    document = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.organization_id == current_user.organization_id,
        )
        .first()
    )

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # 1️⃣ Delete embeddings linked to this document
    db.execute(
        text(
            "DELETE FROM document_embeddings WHERE document_id = :doc_id"
        ),
        {"doc_id": document_id},
    )

    # 2️⃣ Delete physical file from disk
    org_dir = os.path.join("uploads", f"org_{current_user.organization_id}")
    file_path = os.path.join(org_dir, document.filename)

    if os.path.exists(file_path):
        os.remove(file_path)

    # 3️⃣ Delete document metadata
    db.delete(document)
    db.commit()

    return {"message": "Document and embeddings deleted successfully"}
