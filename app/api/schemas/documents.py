from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentOut(BaseModel):
    """Public shape of a document row (list endpoint)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    content_type: str
    uploaded_by: int
    created_at: datetime
    updated_at: datetime


class UploadResponse(BaseModel):
    id: int
    filename: str
    organization_id: int
    chunks_stored: int
