from datetime import datetime
from urllib.parse import urlparse

from pydantic import Field, field_validator, model_validator

from src.attendances.models import AttendanceStatus
from src.core.database import utcnow
from src.core.schemas import CamelModel, UTCDateTime, UTCDateTimeIn
from src.route_calls.models import MeetingPointType, RoutePace, RouteCallStatus
from src.routes.models import RouteLevel
from src.routes.schemas import UserPublicOut


def validate_image_url(value: str | None) -> str | None:
    """Shared by create and update: image must be a valid http(s) URL."""
    if value is None:
        return value
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("Must be a valid URL")
    return value


def validate_future_date(value: datetime) -> datetime:
    """Shared by create and update: a route call date must be in the future."""
    if value <= utcnow():
        raise ValueError("Route call date must be in the future")
    return value


class MeetingPointIn(CamelModel):
    """A meeting point as it arrives in the create body (ported from Express' Zod)."""

    type: MeetingPointType
    name: str = Field(min_length=1)
    custom_name: str | None = None
    location: str | None = None
    time: UTCDateTimeIn | None = None

    @field_validator("location")
    @classmethod
    def _only_google_maps(cls, value: str | None) -> str | None:
        if value is None:
            return value
        host = urlparse(value).hostname or ""
        if not ("google" in host or "maps" in host or "goo.gl" in host):
            raise ValueError(
                "Only Google Maps URLs are allowed (e.g., maps.google.com, goo.gl)"
            )
        return value


class RouteCallCreateIn(CamelModel):
    """Body for POST /api/route-calls (predefined or custom route)."""

    route_id: str | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    image: str | None = None
    date_route: UTCDateTimeIn
    paces: list[RoutePace] = Field(min_length=1, max_length=7)
    meeting_points: list[MeetingPointIn] = Field(min_length=1, max_length=2)

    @field_validator("image")
    @classmethod
    def _image_is_url(cls, value: str | None) -> str | None:
        return validate_image_url(value)

    @field_validator("date_route")
    @classmethod
    def _must_be_in_the_future(cls, value: datetime) -> datetime:
        return validate_future_date(value)

    @model_validator(mode="after")
    def _check_meeting_points(self) -> "RouteCallCreateIn":
        primary = sum(1 for p in self.meeting_points if p.type is MeetingPointType.PRIMARY)
        secondary = sum(1 for p in self.meeting_points if p.type is MeetingPointType.SECONDARY)
        if primary != 1:
            raise ValueError("Exactly one PRIMARY meeting point is required")
        if secondary > 1:
            raise ValueError("Only one SECONDARY meeting point is allowed")
        return self


class RouteCallUpdateIn(CamelModel):
    """Body for PATCH /api/route-calls/{id}: partial update, every field optional."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    image: str | None = None
    date_route: UTCDateTimeIn | None = None
    paces: list[RoutePace] | None = Field(default=None, min_length=1, max_length=7)

    @field_validator("image")
    @classmethod
    def _image_is_url(cls, value: str | None) -> str | None:
        return validate_image_url(value)

    @field_validator("date_route")
    @classmethod
    def _must_be_in_the_future(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return value
        return validate_future_date(value)

    @model_validator(mode="after")
    def _reject_explicit_nulls(self) -> "RouteCallUpdateIn":
        # NOT NULL columns: absent is fine (partial update), explicit null is not
        for field in ("title", "date_route", "paces"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class MeetingPointOut(CamelModel):
    """Meeting point as Express emitted it (the table has no updatedAt)."""

    id: str
    type: MeetingPointType
    name: str
    custom_name: str | None
    location: str | None
    time: UTCDateTime | None
    created_at: UTCDateTime


class RouteSummaryOut(CamelModel):
    """The `select` slice of the route embedded in each route call."""

    id: str
    name: str
    slug: str
    image: str
    approximate_distance: str
    level: list[RouteLevel] | None


class RouteCallCounts(CamelModel):
    """The `_count` block: aggregate counters of the route call's relations."""

    attendances: int


class RouteCallOut(CamelModel):
    """Full route call + relations, as Prisma's `include` emitted it."""

    id: str
    route_id: str | None
    organizer_id: str
    title: str
    description: str | None
    image: str | None
    date_route: UTCDateTime
    paces: list[RoutePace]
    status: RouteCallStatus
    created_at: UTCDateTime
    updated_at: UTCDateTime
    route: RouteSummaryOut | None
    organizer: UserPublicOut
    meeting_points: list[MeetingPointOut]
    # Pydantic forbids field names starting with "_"; an explicit
    # serialization_alias beats the generator and emits the contract's "_count"
    counts: RouteCallCounts = Field(serialization_alias="_count")


class AttendeeOut(CamelModel):
    """A CONFIRMED attendance embedded in the route call detail."""

    id: str
    status: AttendanceStatus
    user: UserPublicOut


class RouteCallDetailOut(RouteCallOut):
    """Detail response: RouteCallOut + the CONFIRMED attendees list."""

    attendances: list[AttendeeOut]