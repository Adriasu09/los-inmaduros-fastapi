from typing import Generic, TypeVar

from pydantic import BaseModel

# The "hole" in the generic: T = whatever type `data` carries in each response.
T = TypeVar("T")


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