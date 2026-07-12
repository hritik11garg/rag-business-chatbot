import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.api.schemas.chat import ChatRequest
from app.core.config import settings
from app.core.ratelimit import limiter
from app.db.models.user import User
from app.composition.chat import build_chat_router_use_case

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("")
@limiter.limit(settings.RATE_LIMIT_CHAT)
def chat(
    request: Request,
    payload: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    use_case = build_chat_router_use_case(db)
    return use_case.execute(
        question=payload.question,
        user=current_user,
        top_k=payload.top_k,
        document_ids=payload.document_ids,
    )


@router.post("/stream")
@limiter.limit(settings.RATE_LIMIT_CHAT)
def chat_stream(
    request: Request,
    payload: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Server-Sent Events: `token` events carry answer fragments as
    they leave the model; the final `done` event carries sources and
    confidence. Data payloads are JSON so newlines survive framing."""
    use_case = build_chat_router_use_case(db)

    def event_source():
        for event, data in use_case.execute_stream(
            question=payload.question,
            user=current_user,
            top_k=payload.top_k,
            document_ids=payload.document_ids,
        ):
            yield f"event: {event}\ndata: {json.dumps(data)}\n\n"

    return StreamingResponse(event_source(), media_type="text/event-stream")
