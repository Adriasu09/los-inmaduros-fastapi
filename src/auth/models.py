import enum
from datetime import datetime
from uuid import uuid4

from sqlalchemy import Enum, text
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base, utcnow


class UserRole(enum.Enum):
    USER = "USER"
    ADMIN = "ADMIN"


class User(Base):
    """Mirror of the existing `users` table (created by Prisma)."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(primary_key=True, default=lambda: str(uuid4()))
    clerk_id: Mapped[str] = mapped_column("clerkId", unique=True)
    email: Mapped[str] = mapped_column(unique=True)
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