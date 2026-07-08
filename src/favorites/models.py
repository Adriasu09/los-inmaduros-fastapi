from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base

if TYPE_CHECKING:
    from src.auth.models import User
    from src.routes.models import Route


class Favorite(Base):
    """Mirror of the existing `favorites` table."""

    __tablename__ = "favorites"
    __table_args__ = (
        UniqueConstraint("routeId", "userId", name="favorites_routeId_userId_key"),
    )

    id: Mapped[str] = mapped_column(primary_key=True, default=lambda: str(uuid4()))
    route_id: Mapped[str] = mapped_column(
        "routeId", ForeignKey("routes.id", ondelete="CASCADE")
    )
    user_id: Mapped[str] = mapped_column(
        "userId", ForeignKey("users.id", ondelete="CASCADE")
    )
    created_at: Mapped[datetime] = mapped_column(
        "createdAt", server_default=text("CURRENT_TIMESTAMP")
    )

    route: Mapped["Route"] = relationship("Route", back_populates="favorites")
    user: Mapped["User"] = relationship("User", back_populates="favorites")
