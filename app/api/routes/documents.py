from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.api.schemas.common import MessageResponse
from app.api.schemas.documents import DocumentOut, UploadResponse
from app.composition.singletons import get_embedding_service
from app.db.models.user import User
from app.tasks.faq_tasks import generate_faqs_task
from app.use_cases.delete_document import DeleteDocumentUseCase, DocumentNotFoundError
from app.use_cases.list_documents import ListDocumentsUseCase
from app.use_cases.upload_document import UploadDocumentUseCase

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=list[DocumentOut])
def list_documents(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    return ListDocumentsUseCase(db).execute(user=current_user)


@router.post("/upload", status_code=201, response_model=UploadResponse)
def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    use_case = UploadDocumentUseCase(
        db,
        embedding_service=get_embedding_service(),
        schedule_faq_generation=lambda chunks, doc_id, org_id: (
            generate_faqs_task.delay(chunks, doc_id, org_id)
        ),
    )
    return use_case.execute(file=file, user=current_user)


@router.delete("/{document_id}", status_code=200, response_model=MessageResponse)
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return DeleteDocumentUseCase(db).execute(
            document_id=document_id,
            user=current_user,
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
