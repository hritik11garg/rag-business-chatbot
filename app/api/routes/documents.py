import os
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.db.models.document import Document
from app.db.models.user import User
from app.services.embedding_service import store_embeddings, store_generated_faq_embeddings
from app.services.document_processing import (
    extract_text_from_pdf,
    normalize_text,
    chunk_text,
)
from app.services.faq_generator import generate_faqs_from_chunk


router = APIRouter(prefix="/documents", tags=["documents"])

UPLOAD_BASE_DIR = "uploads"
@router.post("/upload", status_code=201)
def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload a document for the current user's organization.
    """

    if file.content_type not in {"application/pdf"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are supported",
        )

    # 2️⃣ Create organization-specific upload directory
    org_dir = os.path.join(UPLOAD_BASE_DIR, f"org_{current_user.organization_id}")
    os.makedirs(org_dir, exist_ok=True)

    # 3️⃣ Enterprise-safe filename versioning
    original_name = file.filename
    name, ext = os.path.splitext(original_name)

    counter = 1
    file_path = os.path.join(org_dir, original_name)

    while os.path.exists(file_path):
        counter += 1
        new_name = f"{name}_v{counter}{ext}"
        file_path = os.path.join(org_dir, new_name)

    final_filename = os.path.basename(file_path)

    # 4️⃣ Save file to disk
    try:
        with open(file_path, "wb") as f:
            f.write(file.file.read())
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save uploaded file",
        )

    # 5️⃣ Validate PDF BEFORE DB insert
    try:
        raw_text = extract_text_from_pdf(file_path)
        clean_text = normalize_text(raw_text)
        chunks = chunk_text(clean_text)
    except Exception:
        os.remove(file_path)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded PDF is corrupted or unreadable",
        )

    if not chunks:
        os.remove(file_path)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No readable text found in the document",
        )

    # 6️⃣ Create Document record ONLY after validation
    document = Document(
        filename=final_filename,
        content_type=file.content_type,
        organization_id=current_user.organization_id,
        uploaded_by=current_user.id,
    )

    db.add(document)
    db.commit()
    db.refresh(document)

    # 7️⃣ Generate and store embeddings
    try:
        store_embeddings(
            db=db,
            organization_id=current_user.organization_id,
            document=document,
            chunks=chunks,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate embeddings: {str(e)}",
        )

    # 🤖 Generate FAQs from chunks
    all_faqs = []
    for chunk in chunks:
        faqs = generate_faqs_from_chunk(chunk)
        all_faqs.extend(faqs)

    if all_faqs:
        store_generated_faq_embeddings(
            db,
            organization_id=current_user.organization_id,
            document_id=document.id,
            faqs=all_faqs,
        )

    # 8️⃣ Response
    return {
        "id": document.id,
        "filename": document.filename,
        "organization_id": document.organization_id,
        "chunks_stored": len(chunks),
    }
