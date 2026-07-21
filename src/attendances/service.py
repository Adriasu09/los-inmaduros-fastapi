from sqlalchemy import func, select
from sqlalchemy.orm import Session, contains_eager, joinedload, selectinload

from src.attendances.models import Attendance, AttendanceStatus
from src.attendances.schemas import (
    AttendanceOut,
    CheckOut,
    MyAttendanceOut,
    RouteCallAttendeeOut,
)
from src.core.exceptions import BadRequestError, ConflictError, NotFoundError
from src.route_calls.models import RouteCall, RouteCallStatus
from src.route_calls.service import _to_route_call_out


def _get_attendance(db: Session, route_call_id: str, user_id: str) -> Attendance | None:
    """Fetch the single row for the (route_call_id, user_id) unique, if any."""
    return db.execute(
        select(Attendance).where(
            Attendance.route_call_id == route_call_id,
            Attendance.user_id == user_id,
        )
    ).scalar_one_or_none()


def confirm_attendance(db: Session, user_id: str, route_call_id: str) -> AttendanceOut:
    """Join a route call. Reactivates a previously CANCELLED attendance instead
    of creating a second row — the (routeCallId, userId) unique enforces this
    at the DB level, but the logic must find-and-update on purpose.
    """
    route_call = db.get(RouteCall, route_call_id)
    if route_call is None:
        raise NotFoundError("Route call not found")
    if route_call.status is RouteCallStatus.CANCELLED:
        raise BadRequestError("Cannot attend a cancelled route call")
    if route_call.status is RouteCallStatus.COMPLETED:
        raise BadRequestError("Cannot attend a completed route call")

    attendance = _get_attendance(db, route_call_id, user_id)

    if attendance is not None and attendance.status is AttendanceStatus.CONFIRMED:
        raise ConflictError("You are already attending this route call")

    if attendance is not None and attendance.status is AttendanceStatus.CANCELLED:
        attendance.status = AttendanceStatus.CONFIRMED
    else:
        attendance = Attendance(user_id=user_id, route_call_id=route_call_id)
        db.add(attendance)

    db.commit()
    return AttendanceOut.model_validate(attendance)


def cancel_attendance(db: Session, user_id: str, route_call_id: str) -> AttendanceOut:
    """Cancel my attendance: soft state change to CANCELLED, the row is kept."""
    attendance = _get_attendance(db, route_call_id, user_id)
    if attendance is None:
        raise NotFoundError("Attendance not found")
    if attendance.status is AttendanceStatus.CANCELLED:
        raise BadRequestError("Attendance is already cancelled")

    attendance.status = AttendanceStatus.CANCELLED
    db.commit()
    return AttendanceOut.model_validate(attendance)


def get_route_call_attendances(
    db: Session, route_call_id: str
) -> list[RouteCallAttendeeOut]:
    """Public list of a route call's CONFIRMED attendees, oldest join first."""
    route_call = db.get(RouteCall, route_call_id)
    if route_call is None:
        raise NotFoundError("Route call not found")

    attendances = (
        db.execute(
            select(Attendance)
            .options(joinedload(Attendance.user))
            .where(
                Attendance.route_call_id == route_call_id,
                Attendance.status == AttendanceStatus.CONFIRMED,
            )
            .order_by(Attendance.created_at.asc())
        )
        .scalars()
        .all()
    )
    return [RouteCallAttendeeOut.model_validate(a) for a in attendances]


def check_attendance(db: Session, user_id: str, route_call_id: str) -> CheckOut:
    """Am I attending? True only for a CONFIRMED row.

    Deliberately does NOT verify the route call exists (Express quirk, mirrored):
    a non-existent route call answers {isAttending: false}, never 404.
    """
    attendance = _get_attendance(db, route_call_id, user_id)
    is_attending = (
        attendance is not None and attendance.status is AttendanceStatus.CONFIRMED
    )
    return CheckOut(is_attending=is_attending)


def get_user_attendances(db: Session, user_id: str) -> list[MyAttendanceOut]:
    """My CONFIRMED attendances, soonest route call first, full route call embedded."""
    attendances_count = (
        select(func.count())
        .where(Attendance.route_call_id == RouteCall.id)
        .scalar_subquery()
    )

    rows = db.execute(
        select(Attendance, attendances_count.label("attendances"))
        .join(Attendance.route_call)
        .options(
            contains_eager(Attendance.route_call).joinedload(RouteCall.route),
            contains_eager(Attendance.route_call).joinedload(RouteCall.organizer),
            contains_eager(Attendance.route_call).selectinload(
                RouteCall.meeting_points
            ),
        )
        .where(
            Attendance.user_id == user_id,
            Attendance.status == AttendanceStatus.CONFIRMED,
        )
        .order_by(RouteCall.date_route.asc())
    ).all()

    return [
        MyAttendanceOut(
            id=attendance.id,
            route_call_id=attendance.route_call_id,
            user_id=attendance.user_id,
            status=attendance.status,
            created_at=attendance.created_at,
            updated_at=attendance.updated_at,
            route_call=_to_route_call_out(attendance.route_call, count),
        )
        for attendance, count in rows
    ]
