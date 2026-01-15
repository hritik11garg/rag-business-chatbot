import os
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.db.models.document import Document
from app.db.models.user import User

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

    org_dir = os.path.join(UPLOAD_BASE_DIR, f"org_{current_user.organization_id}")
    os.makedirs(org_dir, exist_ok=True)

    file_path = os.path.join(org_dir, file.filename)

    with open(file_path, "wb") as f:
        f.write(file.file.read())

    document = Document(
        filename=file.filename,
        content_type=file.content_type,
        organization_id=current_user.organization_id,
        uploaded_by=current_user.id,
    )

    db.add(document)
    db.commit()
    db.refresh(document)

    return {
        "id": document.id,
        "filename": document.filename,
        "organization_id": document.organization_id,
    }
