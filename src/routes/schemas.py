from pydantic import Field

from src.core.schemas import CamelModel, Pagination, UTCDateTime
from src.photos.models import PhotoContext, PhotoStatus
from src.routes.models import RouteLevel


class UserPublicOut(CamelModel):
    """Public slice of a user, as embedded in each review (Express' `select`)."""

    id: str
    name: str | None
    image_url: str | None


class ReviewOut(CamelModel):
    """Full review row + its author, as Prisma's `include: { user }` emitted it."""

    id: str
    route_id: str
    user_id: str
    rating: int
    comment: str | None
    created_at: UTCDateTime
    updated_at: UTCDateTime
    user: UserPublicOut


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


class RouteCounts(CamelModel):
    """The `_count` block: aggregate counters of the route's relations."""

    reviews: int
    favorites: int
    route_calls: int
    photos: int


class RouteListItem(CamelModel):
    """Catalogue item: every Route column + average rating + counters."""

    id: str
    name: str
    slug: str
    image: str
    approximate_distance: str
    description: str
    gpx_file_url: str | None
    map_embed_url: str | None
    level: list[RouteLevel] | None
    created_at: UTCDateTime
    updated_at: UTCDateTime
    average_rating: float
    # Pydantic forbids field names starting with "_"; an explicit
    # serialization_alias beats the generator and emits the contract's "_count"
    counts: RouteCounts = Field(serialization_alias="_count")


class RouteDetailOut(RouteListItem):
    """Detail by slug: the catalogue item + a page of reviews + active photos."""

    reviews: list[ReviewOut]
    photos: list[PhotoOut]
    reviews_pagination: Pagination