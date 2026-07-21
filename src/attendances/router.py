from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.attendances import service
from src.attendances.schemas import (
    AttendanceOut,
    CheckOut,
    MyAttendanceOut,
    RouteCallAttendeeOut,
)
from src.auth.deps import get_current_user
from src.auth.models import User
from src.core.database import get_db
from src.core.schemas import ApiResponse

# Nested under a specific route call: /api/route-calls/{route_call_id}/attendances
nested_router = APIRouter(
    prefix="/api/route-calls/{route_call_id}/attendances", tags=["Attendances"]
)

# Flat, not tied to any single route call: /api/attendances
flat_router = APIRouter(prefix="/api/attendances", tags=["Attendances"])


@nested_router.get(
    "/check",
    response_model=ApiResponse[CheckOut],
    response_model_exclude_unset=True,
)
def check_attendance(
    route_call_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = service.check_attendance(db, user.id, str(route_call_id))
    return ApiResponse[CheckOut](success=True, data=result)


@nested_router.post(
    "",
    status_code=201,
    response_model=ApiResponse[AttendanceOut],
    response_model_exclude_unset=True,
)
def confirm_attendance(
    route_call_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    attendance = service.confirm_attendance(db, user.id, str(route_call_id))
    return ApiResponse[AttendanceOut](
        success=True, data=attendance, message="Attendance confirmed successfully"
    )


@nested_router.delete(
    "",
    response_model=ApiResponse[AttendanceOut],
    response_model_exclude_unset=True,
)
def cancel_attendance(
    route_call_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    attendance = service.cancel_attendance(db, user.id, str(route_call_id))
    return ApiResponse[AttendanceOut](
        success=True, data=attendance, message="Attendance cancelled successfully"
    )


@nested_router.get(
    "",
    response_model=ApiResponse[list[RouteCallAttendeeOut]],
    response_model_exclude_unset=True,
)
def get_route_call_attendances(route_call_id: UUID, db: Session = Depends(get_db)):
    attendances = service.get_route_call_attendances(db, str(route_call_id))
    return ApiResponse[list[RouteCallAttendeeOut]](
        success=True, data=attendances, count=len(attendances)
    )


@flat_router.get(
    "/my-attendances",
    response_model=ApiResponse[list[MyAttendanceOut]],
    response_model_exclude_unset=True,
)
def get_user_attendances(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    attendances = service.get_user_attendances(db, user.id)
    return ApiResponse[list[MyAttendanceOut]](
        success=True, data=attendances, count=len(attendances)
    )
