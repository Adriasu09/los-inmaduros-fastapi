import enum
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import Enum, Index, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base, utcnow

if TYPE_CHECKING:
    from src.attendances.models import Attendance
    from src.favorites.models import Favorite
    from src.reviews.models import Review
    from src.route_calls.models import RouteCall
    from src.photos.models import Photo


class UserRole(enum.Enum):
    USER = "USER"
    ADMIN = "ADMIN"


class User(Base):
    """Mirror of the existing `users` table (created by Prisma)."""

    __tablename__ = "users"
    __table_args__ = (
        # Prisma created uniques as named UNIQUE INDEXes: mirror them exactly
        Index("users_clerkId_key", "clerkId", unique=True),
        Index("users_email_key", "email", unique=True),
    )

    id: Mapped[str] = mapped_column(primary_key=True, default=lambda: str(uuid4()))
    clerk_id: Mapped[str] = mapped_column("clerkId")
    email: Mapped[str]
    name: Mapped[str | None]
    last_name: Mapped[str | None] = mapped_column("lastName")
    image_url: Mapped[str | None] = mapped_column("imageUrl")
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="UserRole", create_type=False),
        default=UserRole.USER,
        server_default=text("'USER'::\"UserRole\""),
    )
    created_at: Mapped[datetime] = mapped_column(
        "createdAt", server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        "updatedAt", default=utcnow, onupdate=utcnow
    )

    organized_route_calls: Mapped[list["RouteCall"]] = relationship(
        "RouteCall", back_populates="organizer"
    )
    attendances: Mapped[list["Attendance"]] = relationship(
        "Attendance", back_populates="user"
    )
    reviews: Mapped[list["Review"]] = relationship("Review", back_populates="user")
    favorites: Mapped[list["Favorite"]] = relationship(
        "Favorite", back_populates="user"
    )
    uploaded_photos: Mapped[list["Photo"]] = relationship(
        "Photo", back_populates="user", foreign_keys="Photo.user_id"
    )
    moderated_photos: Mapped[list["Photo"]] = relationship(
        "Photo", back_populates="moderator", foreign_keys="Photo.moderated_by"
    )