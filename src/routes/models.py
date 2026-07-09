import enum
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import Enum, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base, utcnow

if TYPE_CHECKING:
    from src.favorites.models import Favorite
    from src.reviews.models import Review
    from src.route_calls.models import RouteCall
    from src.photos.models import Photo


class RouteLevel(enum.Enum):
    BEGINNER = "BEGINNER"
    INTERMEDIATE = "INTERMEDIATE"
    ADVANCED = "ADVANCED"
    EXPERT = "EXPERT"


class Route(Base):
    """Mirror of the existing `routes` table (the 17 production routes)."""

    __tablename__ = "routes"

    id: Mapped[str] = mapped_column(primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str]
    slug: Mapped[str] = mapped_column(unique=True)
    image: Mapped[str]
    approximate_distance: Mapped[str] = mapped_column("approximateDistance")
    description: Mapped[str]
    gpx_file_url: Mapped[str | None] = mapped_column("gpxFileUrl")
    map_embed_url: Mapped[str | None] = mapped_column("mapEmbedUrl")
    level: Mapped[list[RouteLevel] | None] = mapped_column(
        ARRAY(Enum(RouteLevel, name="RouteLevel", create_type=False))
    )
    created_at: Mapped[datetime] = mapped_column(
        "createdAt", server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        "updatedAt", default=utcnow, onupdate=utcnow
    )

    route_calls: Mapped[list["RouteCall"]] = relationship(
        "RouteCall", back_populates="route"
    )
    reviews: Mapped[list["Review"]] = relationship("Review", back_populates="route")
    favorites: Mapped[list["Favorite"]] = relationship(
        "Favorite", back_populates="route"
    )
    photos: Mapped[list["Photo"]] = relationship("Photo", back_populates="route")