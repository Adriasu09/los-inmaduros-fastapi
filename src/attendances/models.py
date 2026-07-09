import enum
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import Enum, ForeignKey, Index, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base, utcnow

if TYPE_CHECKING:
    from src.auth.models import User
    from src.route_calls.models import RouteCall


class AttendanceStatus(enum.Enum):
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"


class Attendance(Base):
    """Mirror of the existing `attendances` table."""

    __tablename__ = "attendances"
    __table_args__ = (
        # Prisma created this unique as a named UNIQUE INDEX: mirror it exactly
        Index(
            "attendances_routeCallId_userId_key", "routeCallId", "userId", unique=True
        ),
    )

    id: Mapped[str] = mapped_column(primary_key=True, default=lambda: str(uuid4()))
    route_call_id: Mapped[str] = mapped_column(
        "routeCallId",
        ForeignKey("route_calls.id", ondelete="CASCADE", onupdate="CASCADE"),
    )
    user_id: Mapped[str] = mapped_column(
        "userId", ForeignKey("users.id", ondelete="CASCADE", onupdate="CASCADE")
    )
    status: Mapped[AttendanceStatus] = mapped_column(
        Enum(AttendanceStatus, name="AttendanceStatus", create_type=False),
        default=AttendanceStatus.CONFIRMED,
        server_default=text("'CONFIRMED'::\"AttendanceStatus\""),
    )
    created_at: Mapped[datetime] = mapped_column(
        "createdAt", server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        "updatedAt", default=utcnow, onupdate=utcnow
    )

    route_call: Mapped["RouteCall"] = relationship(
        "RouteCall", back_populates="attendances"
    )
    user: Mapped["User"] = relationship("User", back_populates="attendances")