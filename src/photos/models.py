import enum
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import Enum, ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base, utcnow

if TYPE_CHECKING:
    from src.auth.models import User
    from src.route_calls.models import RouteCall
    from src.routes.models import Route


class PhotoContext(enum.Enum):
    ROUTE_CALL_COVER = "ROUTE_CALL_COVER"
    ROUTE_GALLERY = "ROUTE_GALLERY"
    ROUTE_CALL_GALLERY = "ROUTE_CALL_GALLERY"


class PhotoStatus(enum.Enum):
    ACTIVE = "ACTIVE"
    FLAGGED = "FLAGGED"
    REJECTED = "REJECTED"
    DELETED = "DELETED"


class Photo(Base):
    """Mirror of the existing `photos` table."""

    __tablename__ = "photos"

    id: Mapped[str] = mapped_column(primary_key=True, default=lambda: str(uuid4()))
    context: Mapped[PhotoContext] = mapped_column(
        Enum(PhotoContext, name="PhotoContext", create_type=False),
        default=PhotoContext.ROUTE_GALLERY,
        server_default=text("'ROUTE_GALLERY'::\"PhotoContext\""),
    )
    route_id: Mapped[str | None] = mapped_column(
        "routeId", ForeignKey("routes.id", ondelete="SET NULL")
    )
    route_call_id: Mapped[str | None] = mapped_column(
        "routeCallId", ForeignKey("route_calls.id", ondelete="SET NULL")
    )
    user_id: Mapped[str] = mapped_column(
        "userId", ForeignKey("users.id", ondelete="CASCADE")
    )
    image_url: Mapped[str] = mapped_column("imageUrl")
    caption: Mapped[str | None]
    status: Mapped[PhotoStatus] = mapped_column(
        Enum(PhotoStatus, name="PhotoStatus", create_type=False),
        default=PhotoStatus.ACTIVE,
        server_default=text("'ACTIVE'::\"PhotoStatus\""),
    )
    moderated_at: Mapped[datetime | None] = mapped_column("moderatedAt")
    moderated_by: Mapped[str | None] = mapped_column(
        "moderatedBy", ForeignKey("users.id", ondelete="SET NULL")
    )
    moderation_notes: Mapped[str | None] = mapped_column("moderationNotes")
    created_at: Mapped[datetime] = mapped_column(
        "createdAt", server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        "updatedAt", default=utcnow, onupdate=utcnow
    )

    route: Mapped["Route | None"] = relationship("Route", back_populates="photos")
    route_call: Mapped["RouteCall | None"] = relationship(
        "RouteCall", back_populates="photos"
    )
    user: Mapped["User"] = relationship(
        "User", back_populates="uploaded_photos", foreign_keys=[user_id]
    )
    moderator: Mapped["User | None"] = relationship(
        "User", back_populates="moderated_photos", foreign_keys=[moderated_by]
    )