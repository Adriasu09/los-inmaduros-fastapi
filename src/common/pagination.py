import math

from src.core.schemas import Pagination


def build_pagination(page: int, limit: int, total_count: int) -> Pagination:
    """Build the contract's pagination block (parity with Express routes.service)."""
    total_pages = math.ceil(total_count / limit)
    return Pagination(
        page=page,
        limit=limit,
        total_count=total_count,
        total_pages=total_pages,
        has_next_page=page < total_pages,
        has_previous_page=page > 1,
    )