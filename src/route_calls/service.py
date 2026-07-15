from datetime import datetime, timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from src.attendances.models import Attendance
from src.common.pagination import build_pagination
from src.core.database import utcnow
from src.core.exceptions import BadRequestError, NotFoundError
from src.core.schemas import Pagination
from src.route_calls.models import (
    MeetingPoint,
    RouteCall,
    RouteCallStatus,
    RoutePace,
)
from src.route_calls.schemas import (
    MeetingPointOut,
    RouteCallCounts,
    RouteCallCreateIn,
    RouteCallOut,
    RouteSummaryOut,
)
from src.routes.models import Route
from src.routes.schemas import UserPublicOut

# Copied verbatim from Express (route-calls.service.ts)
DEFAULT_ROUTE_CALL_IMAGE = (
    "https://res.cloudinary.com/dj4j3uoia/image/upload/v1726855799/otraRuta_az0ggq.jpg"
)


def _to_route_call_out(route_call: RouteCall, attendances: int) -> RouteCallOut:
    """Serialize a route call with its relations (meeting points PRIMARY first)."""
    ordered_points = sorted(route_call.meeting_points, key=lambda p: p.type.value)
    return RouteCallOut(
        id=route_call.id,
        route_id=route_call.route_id,
        organizer_id=route_call.organizer_id,
        title=route_call.title,
        description=route_call.description,
        image=route_call.image,
        date_route=route_call.date_route,
        paces=route_call.paces,
        status=route_call.status,
        created_at=route_call.created_at,
        updated_at=route_call.updated_at,
        route=(
            RouteSummaryOut.model_validate(route_call.route)
            if route_call.route
            else None
        ),
        organizer=UserPublicOut.model_validate(route_call.organizer),
        meeting_points=[MeetingPointOut.model_validate(p) for p in ordered_points],
        counts=RouteCallCounts(attendances=attendances),
    )


def create_route_call(
    db: Session, organizer_id: str, data: RouteCallCreateIn
) -> RouteCallOut:
    """Create a route call (predefined or custom route) with its meeting points."""
    if data.route_id:
        route = db.get(Route, data.route_id)
        if route is None:
            raise NotFoundError("Route not found")
        # Predefined route: the route's name wins over any client-sent title
        title = route.name
        image = data.image or route.image or DEFAULT_ROUTE_CALL_IMAGE
    else:
        if not data.title:
            raise BadRequestError("Title is required for custom routes")
        title = data.title
        image = data.image or DEFAULT_ROUTE_CALL_IMAGE

    route_call = RouteCall(
        route_id=data.route_id,
        organizer_id=organizer_id,
        title=title,
        description=data.description,
        image=image,
        date_route=data.date_route,
        paces=data.paces,
        meeting_points=[
            MeetingPoint(
                type=point.type,
                name=point.name,
                custom_name=point.custom_name,
                location=point.location,
                time=point.time,
            )
            for point in data.meeting_points
        ],
    )
    db.add(route_call)
    db.commit()

    # A just-born route call cannot have attendances yet
    return _to_route_call_out(route_call, attendances=0)


def list_route_calls(
    db: Session,
    *,
    status: RouteCallStatus | None = None,
    organizer_id: str | None = None,
    route_id: str | None = None,
    upcoming: bool | None = None,
    pace: RoutePace | None = None,
    month: str | None = None,
    page: int = 1,
    limit: int = 20,
) -> tuple[list[RouteCallOut], Pagination]:
    """List route calls with composable filters, ordered by dateRoute."""
    conditions = []

    if status is not None:
        conditions.append(RouteCall.status == status)
    if organizer_id is not None:
        conditions.append(RouteCall.organizer_id == organizer_id)
    if route_id is not None:
        conditions.append(RouteCall.route_id == route_id)

    if upcoming is not None:
        # Product rule: a CANCELLED route call stays "upcoming" for 2 hours
        # past its dateRoute, so people SEE it was cancelled (parity with Express)
        two_hours_ago = utcnow() - timedelta(hours=2)
        if upcoming:
            conditions.append(
                or_(
                    RouteCall.status == RouteCallStatus.SCHEDULED,
                    RouteCall.status == RouteCallStatus.ONGOING,
                    and_(
                        RouteCall.status == RouteCallStatus.CANCELLED,
                        RouteCall.date_route >= two_hours_ago,
                    ),
                )
            )
        else:
            conditions.append(
                or_(
                    RouteCall.status == RouteCallStatus.COMPLETED,
                    and_(
                        RouteCall.status == RouteCallStatus.CANCELLED,
                        RouteCall.date_route < two_hours_ago,
                    ),
                )
            )

    if pace is not None:
        conditions.append(RouteCall.paces.contains([pace]))

    if month is not None:
        year, month_number = map(int, month.split("-"))
        start = datetime(year, month_number, 1)
        if month_number == 12:
            next_start = datetime(year + 1, 1, 1)
        else:
            next_start = datetime(year, month_number + 1, 1)
        conditions.append(RouteCall.date_route >= start)
        conditions.append(RouteCall.date_route < next_start)

    total_count = db.execute(
        select(func.count()).select_from(RouteCall).where(*conditions)
    ).scalar_one()

    # Past listings read newest-first; upcoming ones, soonest-first (Express parity)
    order = (
        RouteCall.date_route.desc()
        if upcoming is False
        else RouteCall.date_route.asc()
    )

    attendances_count = (
        select(func.count())
        .where(Attendance.route_call_id == RouteCall.id)
        .scalar_subquery()
    )

    rows = db.execute(
        select(RouteCall, attendances_count.label("attendances"))
        .options(
            joinedload(RouteCall.route),
            joinedload(RouteCall.organizer),
            selectinload(RouteCall.meeting_points),
        )
        .where(*conditions)
        .order_by(order)
        .offset((page - 1) * limit)
        .limit(limit)
    ).all()

    items = [_to_route_call_out(route_call, count) for route_call, count in rows]
    return items, build_pagination(page, limit, total_count)