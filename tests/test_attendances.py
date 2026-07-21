from datetime import timedelta

import pytest
from sqlalchemy import func, select

from src.attendances.models import Attendance, AttendanceStatus
from src.core.database import utcnow
from src.route_calls.models import RouteCallStatus
from tests.test_route_calls import make_attendance, make_route_call

FUTURE = utcnow() + timedelta(days=7)
RANDOM_UUID = "00000000-0000-0000-0000-000000000000"


@pytest.fixture()
def attendee(as_user, db_session):
    """The authenticated fake user, persisted: attendances reference its userId FK."""
    db_session.add(as_user)
    db_session.commit()  # savepoint, evaporates on rollback
    return as_user


def _count_rows(db_session, route_call_id, user_id) -> int:
    """Number of attendance rows for a (route call, user) pair — for the no-dup checks."""
    return db_session.execute(
        select(func.count())
        .select_from(Attendance)
        .where(
            Attendance.route_call_id == route_call_id,
            Attendance.user_id == user_id,
        )
    ).scalar_one()


# --- POST /api/route-calls/{id}/attendances (join) -------------------------


def test_join_scheduled_returns_201_confirmed(
    client_db, attendee, db_session, make_user
):
    route_call = make_route_call(
        db_session, make_user(), RouteCallStatus.SCHEDULED, FUTURE
    )

    response = client_db.post(f"/api/route-calls/{route_call.id}/attendances")

    assert response.status_code == 201
    body = response.json()
    assert body["message"] == "Attendance confirmed successfully"
    data = body["data"]
    assert data["status"] == "CONFIRMED"
    assert data["routeCallId"] == route_call.id
    assert data["userId"] == attendee.id
    # D19: POST returns the flat attendance — no embedded user/routeCall
    assert set(data) == {
        "id",
        "routeCallId",
        "userId",
        "status",
        "createdAt",
        "updatedAt",
    }


@pytest.mark.parametrize(
    "status, message",
    [
        (RouteCallStatus.CANCELLED, "Cannot attend a cancelled route call"),
        (RouteCallStatus.COMPLETED, "Cannot attend a completed route call"),
    ],
    ids=["cancelled", "completed"],
)
def test_join_closed_route_call_returns_400(
    client_db, attendee, db_session, make_user, status, message
):
    route_call = make_route_call(db_session, make_user(), status, FUTURE)

    response = client_db.post(f"/api/route-calls/{route_call.id}/attendances")

    assert response.status_code == 400
    assert response.json()["message"] == message


def test_join_twice_returns_409(client_db, attendee, db_session, make_user):
    route_call = make_route_call(
        db_session, make_user(), RouteCallStatus.SCHEDULED, FUTURE
    )
    make_attendance(db_session, route_call, attendee, AttendanceStatus.CONFIRMED)

    response = client_db.post(f"/api/route-calls/{route_call.id}/attendances")

    assert response.status_code == 409
    assert response.json()["message"] == "You are already attending this route call"


def test_rejoin_after_cancelling_returns_201_confirmed(
    client_db, attendee, db_session, make_user
):
    route_call = make_route_call(
        db_session, make_user(), RouteCallStatus.SCHEDULED, FUTURE
    )
    make_attendance(db_session, route_call, attendee, AttendanceStatus.CANCELLED)

    response = client_db.post(f"/api/route-calls/{route_call.id}/attendances")

    assert response.status_code == 201
    assert response.json()["data"]["status"] == "CONFIRMED"


def test_join_without_auth_returns_401(client_db, db_session, make_user):
    route_call = make_route_call(
        db_session, make_user(), RouteCallStatus.SCHEDULED, FUTURE
    )

    response = client_db.post(f"/api/route-calls/{route_call.id}/attendances")

    assert response.status_code == 401
    assert response.json()["success"] is False


def test_join_with_non_uuid_id_returns_400(client_db, attendee):
    response = client_db.post("/api/route-calls/not-a-uuid/attendances")

    assert response.status_code == 400
    assert response.json()["success"] is False


# --- DELETE /api/route-calls/{id}/attendances (cancel) ---------------------


def test_cancel_confirmed_returns_200_and_keeps_the_row(
    client_db, attendee, db_session, make_user
):
    route_call = make_route_call(
        db_session, make_user(), RouteCallStatus.SCHEDULED, FUTURE
    )
    make_attendance(db_session, route_call, attendee, AttendanceStatus.CONFIRMED)

    response = client_db.delete(f"/api/route-calls/{route_call.id}/attendances")

    assert response.status_code == 200
    assert response.json()["message"] == "Attendance cancelled successfully"
    assert response.json()["data"]["status"] == "CANCELLED"
    # Soft cancel: the row survives, only its status changed
    assert _count_rows(db_session, route_call.id, attendee.id) == 1


def test_cancel_without_attendance_returns_404(
    client_db, attendee, db_session, make_user
):
    route_call = make_route_call(
        db_session, make_user(), RouteCallStatus.SCHEDULED, FUTURE
    )

    response = client_db.delete(f"/api/route-calls/{route_call.id}/attendances")

    assert response.status_code == 404
    assert response.json()["message"] == "Attendance not found"


def test_cancel_already_cancelled_returns_400(
    client_db, attendee, db_session, make_user
):
    route_call = make_route_call(
        db_session, make_user(), RouteCallStatus.SCHEDULED, FUTURE
    )
    make_attendance(db_session, route_call, attendee, AttendanceStatus.CANCELLED)

    response = client_db.delete(f"/api/route-calls/{route_call.id}/attendances")

    assert response.status_code == 400
    assert response.json()["message"] == "Attendance is already cancelled"


# --- GET /api/route-calls/{id}/attendances (public list) -------------------


def test_list_returns_only_confirmed_attendees(client_db, db_session, make_user):
    route_call = make_route_call(
        db_session, make_user(), RouteCallStatus.SCHEDULED, FUTURE
    )
    first = make_user()
    second = make_user()
    make_attendance(db_session, route_call, first, AttendanceStatus.CONFIRMED)
    make_attendance(db_session, route_call, second, AttendanceStatus.CONFIRMED)
    make_attendance(
        db_session, route_call, make_user(), AttendanceStatus.CANCELLED
    )

    # Public: no auth fixture in play
    response = client_db.get(f"/api/route-calls/{route_call.id}/attendances")

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 2
    returned_users = {item["user"]["id"] for item in body["data"]}
    assert returned_users == {first.id, second.id}  # the CANCELLED one is excluded
    # D19: the attendee slice unified to UserPublicOut — no lastName
    assert "lastName" not in body["data"][0]["user"]


def test_list_of_unknown_route_call_returns_404(client_db):
    response = client_db.get(f"/api/route-calls/{RANDOM_UUID}/attendances")

    assert response.status_code == 404
    assert response.json()["message"] == "Route call not found"


# --- GET /api/route-calls/{id}/attendances/check ---------------------------


def test_check_true_when_confirmed(client_db, attendee, db_session, make_user):
    route_call = make_route_call(
        db_session, make_user(), RouteCallStatus.SCHEDULED, FUTURE
    )
    make_attendance(db_session, route_call, attendee, AttendanceStatus.CONFIRMED)

    response = client_db.get(f"/api/route-calls/{route_call.id}/attendances/check")

    assert response.status_code == 200
    assert response.json()["data"]["isAttending"] is True


def test_check_false_when_cancelled(client_db, attendee, db_session, make_user):
    route_call = make_route_call(
        db_session, make_user(), RouteCallStatus.SCHEDULED, FUTURE
    )
    make_attendance(db_session, route_call, attendee, AttendanceStatus.CANCELLED)

    response = client_db.get(f"/api/route-calls/{route_call.id}/attendances/check")

    assert response.status_code == 200
    assert response.json()["data"]["isAttending"] is False


def test_check_unknown_route_call_returns_404(client_db, attendee):
    # D20: unlike Express, check validates the route call exists
    response = client_db.get(f"/api/route-calls/{RANDOM_UUID}/attendances/check")

    assert response.status_code == 404
    assert response.json()["message"] == "Route call not found"


# --- GET /api/attendances/my-attendances -----------------------------------


def test_my_attendances_returns_only_mine_confirmed_soonest_first(
    client_db, attendee, db_session, make_user
):
    organizer = make_user()
    soon = make_route_call(
        db_session, organizer, RouteCallStatus.SCHEDULED, utcnow() + timedelta(days=2)
    )
    later = make_route_call(
        db_session, organizer, RouteCallStatus.SCHEDULED, utcnow() + timedelta(days=10)
    )
    cancelled_one = make_route_call(
        db_session, organizer, RouteCallStatus.SCHEDULED, FUTURE
    )
    make_attendance(db_session, soon, attendee, AttendanceStatus.CONFIRMED)
    make_attendance(db_session, later, attendee, AttendanceStatus.CONFIRMED)
    make_attendance(db_session, cancelled_one, attendee, AttendanceStatus.CANCELLED)
    # Someone else's attendance must never leak into MY list
    make_attendance(db_session, soon, make_user(), AttendanceStatus.CONFIRMED)

    response = client_db.get("/api/attendances/my-attendances")

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 2
    # Only my CONFIRMED, ordered by the route call's dateRoute ascending
    assert [item["routeCall"]["id"] for item in body["data"]] == [soon.id, later.id]
    # my-attendances embeds the full route call (unlike POST/DELETE)
    assert body["data"][0]["routeCall"]["organizer"]["id"] == organizer.id


def test_my_attendances_without_auth_returns_401(client_db):
    response = client_db.get("/api/attendances/my-attendances")

    assert response.status_code == 401
    assert response.json()["success"] is False


# --- Reactivation invariant: one row per (route call, user) ----------------


def test_rejoining_reuses_the_same_record(
    client_db, attendee, db_session, make_user
):
    route_call = make_route_call(
        db_session, make_user(), RouteCallStatus.SCHEDULED, FUTURE
    )
    make_attendance(db_session, route_call, attendee, AttendanceStatus.CANCELLED)

    response = client_db.post(f"/api/route-calls/{route_call.id}/attendances")

    assert response.status_code == 201
    # The capital rule: reactivation UPDATES the row, never INSERTs a second one
    assert _count_rows(db_session, route_call.id, attendee.id) == 1
    reused = db_session.execute(
        select(Attendance).where(
            Attendance.route_call_id == route_call.id,
            Attendance.user_id == attendee.id,
        )
    ).scalar_one()
    assert reused.status is AttendanceStatus.CONFIRMED
