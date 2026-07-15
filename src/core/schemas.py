from datetime import datetime, timezone
from typing import Annotated, Generic, TypeVar

from pydantic import AfterValidator, BaseModel, ConfigDict, PlainSerializer
from pydantic.alias_generators import to_camel

# The "hole" in the generic: T = whatever type `data` carries in each response.
T = TypeVar("T")


class CamelModel(BaseModel):
    """Base for all contract-facing schemas: snake_case inside, camelCase outside."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class Pagination(CamelModel):
    """Pagination block, exactly as the Express API returns it (camelCase)."""

    page: int
    limit: int
    total_count: int
    total_pages: int
    has_next_page: bool
    has_previous_page: bool


class ApiResponse(BaseModel, Generic[T]):
    """Envelope for ALL API responses — the frontend depends on this shape."""

    success: bool
    data: T | None = None
    message: str | None = None
    count: int | None = None
    pagination: Pagination | None = None


def _serialize_utc_z(dt: datetime) -> str:
    """Emit naive-UTC datetimes exactly like JS Date.toISOString(): '...T...sss Z'."""
    return dt.isoformat(timespec="milliseconds") + "Z"


UTCDateTime = Annotated[datetime, PlainSerializer(_serialize_utc_z, return_type=str)]


def _normalize_to_naive_utc(value: object) -> object:
    """Convert incoming aware datetimes to naive UTC (project convention for storage)."""
    if isinstance(value, datetime) and value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


UTCDateTimeIn = Annotated[datetime, AfterValidator(_normalize_to_naive_utc)]