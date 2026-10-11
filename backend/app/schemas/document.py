import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.document import DocStatus, ReviewStatus


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    source_filename: str | None
    language: str | None
    topic_tags: list[str]
    status: DocStatus
    review_status: ReviewStatus
    review_notes: str | None
    version: int
    checksum: str | None
    created_at: datetime
    indexed_at: datetime | None


class ReviewIn(BaseModel):
    status: ReviewStatus
    notes: str | None = None
