from datetime import datetime
from typing import Annotated, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, PlainSerializer
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


class Pagination(BaseModel):
    """Pagination block, exactly as the Express API returns it (camelCase)."""

    page: int
    limit: int
    totalCount: int
    totalPages: int
    hasNextPage: bool
    hasPreviousPage: bool


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