from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.db.models.user import User
from app.composition.chat import build_chat_use_case

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("")
def chat(
    question: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    use_case = build_chat_use_case(db)
    return use_case.execute(
        question=question,
        user=current_user,
    )
