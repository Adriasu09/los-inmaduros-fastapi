from src.core.schemas import CamelModel, UTCDateTime
from src.photos.models import PhotoContext, PhotoStatus


class PhotoOut(CamelModel):
    """Full photo row — Prisma had no `select` on photos, so Express emitted every column."""

    id: str
    context: PhotoContext
    route_id: str | None
    route_call_id: str | None
    user_id: str
    image_url: str
    caption: str | None
    status: PhotoStatus
    moderated_at: UTCDateTime | None
    moderated_by: str | None
    moderation_notes: str | None
    created_at: UTCDateTime
    updated_at: UTCDateTime
