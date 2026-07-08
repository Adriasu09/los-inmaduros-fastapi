from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base, utcnow

if TYPE_CHECKING:
    from src.auth.models import User
    from src.routes.models import Route


class Review(Base):
    """Mirror of the existing `reviews` table."""

    __tablename__ = "reviews"
    __table_args__ = (
        UniqueConstraint(
            "userId", "routeId", name="reviews_userId_routeId_key"
        ),
    )

    id: Mapped[str] = mapped_column(primary_key=True, default=lambda: str(uuid4()))
    route_id: Mapped[str] = mapped_column(
        "routeId", ForeignKey("routes.id", ondelete="CASCADE")
    )
    user_id: Mapped[str] = mapped_column(
        "userId", ForeignKey("users.id", ondelete="CASCADE")
    )
    rating: Mapped[int]
    comment: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(
        "createdAt", server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        "updatedAt", default=utcnow, onupdate=utcnow
    )

    route: Mapped["Route"] = relationship("Route", back_populates="reviews")
    user: Mapped["User"] = relationship("User", back_populates="reviews")

