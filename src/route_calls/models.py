import enum
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import Enum, ForeignKey, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base, utcnow

if TYPE_CHECKING:
    from src.auth.models import User
    from src.routes.models import Route
    from src.attendances.models import Attendance
    from src.photos.models import Photo


class RoutePace(enum.Enum):
    ROCA = "ROCA"
    CARACOL = "CARACOL"
    GUSANO = "GUSANO"
    MARIPOSA = "MARIPOSA"
    EXPERIMENTADO = "EXPERIMENTADO"
    LOCURA_TOTAL = "LOCURA_TOTAL"
    MIAUCORNIA = "MIAUCORNIA"


class RouteCallStatus(enum.Enum):
    SCHEDULED = "SCHEDULED"
    ONGOING = "ONGOING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class MeetingPointType(enum.Enum):
    PRIMARY = "PRIMARY"
    SECONDARY = "SECONDARY"


class RouteCall(Base):
    """Mirror of the existing `route_calls` table."""

    __tablename__ = "route_calls"

    id: Mapped[str] = mapped_column(primary_key=True, default=lambda: str(uuid4()))
    route_id: Mapped[str | None] = mapped_column(
        "routeId", ForeignKey("routes.id", ondelete="SET NULL", onupdate="CASCADE")
    )
    organizer_id: Mapped[str] = mapped_column(
        "organizerId", ForeignKey("users.id", ondelete="CASCADE", onupdate="CASCADE")
    )
    title: Mapped[str]
    description: Mapped[str | None]
    image: Mapped[str | None]
    date_route: Mapped[datetime] = mapped_column("dateRoute")
    paces: Mapped[list[RoutePace]] = mapped_column(
        ARRAY(Enum(RoutePace, name="RoutePace", create_type=False))
    )
    status: Mapped[RouteCallStatus] = mapped_column(
        Enum(RouteCallStatus, name="RouteCallStatus", create_type=False),
        default=RouteCallStatus.SCHEDULED,
        server_default=text("'SCHEDULED'::\"RouteCallStatus\""),
    )
    created_at: Mapped[datetime] = mapped_column(
        "createdAt", server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        "updatedAt", default=utcnow, onupdate=utcnow
    )

    route: Mapped["Route | None"] = relationship(
        "Route", back_populates="route_calls"
    )
    organizer: Mapped["User"] = relationship(
        "User", back_populates="organized_route_calls"
    )
    meeting_points: Mapped[list["MeetingPoint"]] = relationship(
        "MeetingPoint",
        back_populates="route_call",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    attendances: Mapped[list["Attendance"]] = relationship(
        "Attendance", back_populates="route_call"
    )
    photos: Mapped[list["Photo"]] = relationship("Photo", back_populates="route_call")


class MeetingPoint(Base):
    """Mirror of the existing `meeting_points` table."""

    __tablename__ = "meeting_points"

    id: Mapped[str] = mapped_column(primary_key=True, default=lambda: str(uuid4()))
    route_call_id: Mapped[str] = mapped_column(
        "routeCallId",
        ForeignKey("route_calls.id", ondelete="CASCADE", onupdate="CASCADE"),
    )
    type: Mapped[MeetingPointType] = mapped_column(
        Enum(MeetingPointType, name="MeetingPointType", create_type=False),
        default=MeetingPointType.PRIMARY,
        server_default=text("'PRIMARY'::\"MeetingPointType\""),
    )
    name: Mapped[str]
    custom_name: Mapped[str | None] = mapped_column("customName")
    location: Mapped[str | None]
    time: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(
        "createdAt", server_default=text("CURRENT_TIMESTAMP")
    )

    route_call: Mapped["RouteCall"] = relationship(
        "RouteCall", back_populates="meeting_points"
    )