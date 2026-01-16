from fastapi import FastAPI, Depends
from contextlib import asynccontextmanager
from app.core.config import settings
from app.api.deps import get_current_user
from app.db.base import Base
from app.db.session import engine
from app.db import models  # noqa: F401
from app.api.routes import auth, documents, chat
from app.db.models.user import User



@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan event handler.
    Runs once on application startup and shutdown.
    """

    # --- Startup logic ---
    Base.metadata.create_all(bind=engine)

    yield

    # --- Shutdown logic ---
    # (Nothing to clean up yet)


app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    lifespan=lifespan
)


@app.get("/health", tags=["system"])
def health_check():
    """
    Health check endpoint for monitoring.
    """
    return {"status": "ok"}

@app.get("/me")
def read_me(current_user: User = Depends(get_current_user)):
    """
    Test protected endpoint.
    """
    return {
        "id": current_user.id,
        "email": current_user.email,
        "organization_id": current_user.organization_id,
    }

app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(chat.router)

