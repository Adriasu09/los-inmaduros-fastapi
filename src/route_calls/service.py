from sqlalchemy.orm import Session

from src.core.exceptions import BadRequestError, NotFoundError
from src.route_calls.models import MeetingPoint, RouteCall
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