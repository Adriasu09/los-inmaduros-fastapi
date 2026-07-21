from src.attendances.models import AttendanceStatus
from src.core.schemas import CamelModel, UTCDateTime
from src.route_calls.schemas import RouteCallOut
from src.routes.schemas import UserPublicOut


class AttendanceOut(CamelModel):
    """Flat attendance row — the shared base for every attendance response."""

    id: str
    route_call_id: str
    user_id: str
    status: AttendanceStatus
    created_at: UTCDateTime
    updated_at: UTCDateTime


class RouteCallAttendeeOut(AttendanceOut):
    """A CONFIRMED attendance as the public attendees list emits it: base + user."""

    user: UserPublicOut


class CheckOut(CamelModel):
    """Body of GET .../attendances/check — just the boolean flag."""

    is_attending: bool


class MyAttendanceOut(AttendanceOut):
    """One of my CONFIRMED attendances: base + the full route call it belongs to."""

    route_call: RouteCallOut
