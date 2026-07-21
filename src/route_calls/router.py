from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.auth.deps import get_current_user
from src.auth.models import User
from src.core.database import get_db
from src.core.schemas import ApiResponse
from src.route_calls import service
from src.route_calls.models import RouteCallStatus, RoutePace
from src.route_calls.schemas import (
    RouteCallCreateIn,
    RouteCallDetailOut,
    RouteCallOut,
    RouteCallUpdateIn,
)

router = APIRouter(prefix="/api/route-calls", tags=["Route Calls"])


@router.post(
    "",
    status_code=201,
    response_model=ApiResponse[RouteCallOut],
    response_model_exclude_unset=True,
)
def create_route_call(
    data: RouteCallCreateIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    route_call = service.create_route_call(db, user.id, data)
    return ApiResponse[RouteCallOut](
        success=True, data=route_call, message="Route call created successfully"
    )


@router.get(
    "",
    response_model=ApiResponse[list[RouteCallOut]],
    response_model_exclude_unset=True,
)
def list_route_calls(
    db: Session = Depends(get_db),
    status: RouteCallStatus | None = None,
    organizer_id: str | None = Query(None, alias="organizerId"),
    route_id: str | None = Query(None, alias="routeId"),
    upcoming: bool | None = None,
    pace: RoutePace | None = None,
    month: str | None = Query(None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    route_calls, pagination = service.list_route_calls(
        db,
        status=status,
        organizer_id=organizer_id,
        route_id=route_id,
        upcoming=upcoming,
        pace=pace,
        month=month,
        page=page,
        limit=limit,
    )
    return ApiResponse[list[RouteCallOut]](
        success=True, data=route_calls, pagination=pagination
    )


@router.get(
    "/{route_call_id}",
    response_model=ApiResponse[RouteCallDetailOut],
    response_model_exclude_unset=True,
)
def get_route_call_by_id(
    route_call_id: UUID,
    db: Session = Depends(get_db),
):
    route_call = service.get_route_call_by_id(db, str(route_call_id))
    return ApiResponse[RouteCallDetailOut](success=True, data=route_call)


@router.patch(
    "/{route_call_id}",
    response_model=ApiResponse[RouteCallOut],
    response_model_exclude_unset=True,
)
def update_route_call(
    route_call_id: UUID,
    data: RouteCallUpdateIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    route_call = service.update_route_call(db, str(route_call_id), user.id, data)
    return ApiResponse[RouteCallOut](
        success=True, data=route_call, message="Route call updated successfully"
    )


@router.patch(
    "/{route_call_id}/cancel",
    response_model=ApiResponse[RouteCallOut],
    response_model_exclude_unset=True,
)
def cancel_route_call(
    route_call_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    route_call = service.cancel_route_call(db, str(route_call_id), user.id, user.role)
    return ApiResponse[RouteCallOut](
        success=True, data=route_call, message="Route call cancelled successfully"
    )


@router.delete(
    "/{route_call_id}",
    response_model=ApiResponse[dict],
    response_model_exclude_unset=True,
)
def delete_route_call(
    route_call_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service.delete_route_call(db, str(route_call_id), user.id, user.role)
    return ApiResponse[dict](success=True, message="Route call deleted successfully")