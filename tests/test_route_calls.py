from datetime import timedelta

import pytest
from sqlalchemy import func, select

from src.attendances.models import Attendance, AttendanceStatus
from src.core.database import utcnow
from src.route_calls.models import MeetingPoint, RouteCall, RouteCallStatus, RoutePace
from src.routes.models import Route

FUTURE = utcnow() + timedelta(days=7)

PRIMARY_POINT = {
    "type": "PRIMARY",
    "name": "Explanada",
    "location": "https://maps.app.goo.gl/gCJfpLSoy3D454Y19",
}
SECONDARY_POINT = {"type": "SECONDARY", "name": "Puerta de Alcalá"}


def valid_payload(**overrides) -> dict:
    """Minimal valid custom-route body; tests mutate it via overrides."""
    payload = {
        "title": "Ruta de prueba",
        "dateRoute": FUTURE.isoformat() + "Z",
        "paces": ["MARIPOSA"],
        "meetingPoints": [PRIMARY_POINT],
    }
    payload.update(overrides)
    return payload


@pytest.fixture()
def organizer(as_user, db_session):
    """The authenticated fake user, persisted inside the savepoint bubble:
    the POST inserts a real row whose organizerId FK must exist."""
    db_session.add(as_user)
    db_session.commit()  # savepoint, evaporates on rollback
    return as_user


def make_route_call(db_session, organizer, status, date_route) -> RouteCall:
    """Synthetic listing row (no meeting points needed for filter tests)."""
    route_call = RouteCall(
        organizer_id=organizer.id,
        title="Synthetic",
        image="https://example.com/x.jpg",
        date_route=date_route,
        paces=[RoutePace.MARIPOSA],
        status=status,
    )
    db_session.add(route_call)
    db_session.commit()
    return route_call


def make_attendance(db_session, route_call, user, status=AttendanceStatus.CONFIRMED):
    """Synthetic attendance row inside the savepoint bubble."""
    attendance = Attendance(
        route_call_id=route_call.id, user_id=user.id, status=status
    )
    db_session.add(attendance)
    db_session.commit()
    return attendance


# --- POST /api/route-calls -------------------------------------------------


def test_create_with_predefined_route_overrides_title(client_db, organizer, db_session):
    route = db_session.execute(select(Route)).scalars().first()

    response = client_db.post(
        "/api/route-calls",
        json=valid_payload(
            routeId=route.id,
            title="Este título debe ser ignorado",
            meetingPoints=[SECONDARY_POINT, PRIMARY_POINT],
        ),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Route call created successfully"
    data = body["data"]
    assert data["title"] == route.name  # the route's name wins
    assert data["status"] == "SCHEDULED"
    assert data["organizer"]["id"] == organizer.id
    assert data["route"]["slug"] == route.slug
    # PRIMARY first, even though the payload sent SECONDARY first
    assert [p["type"] for p in data["meetingPoints"]] == ["PRIMARY", "SECONDARY"]


def test_create_custom_without_title_returns_400_with_exact_message(
    client_db, organizer
):
    payload = valid_payload()
    del payload["title"]

    response = client_db.post("/api/route-calls", json=payload)

    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert body["message"] == "Title is required for custom routes"


def test_create_with_unknown_route_returns_404(client_db, organizer):
    response = client_db.post(
        "/api/route-calls",
        json=valid_payload(routeId="00000000-0000-0000-0000-000000000000"),
    )

    assert response.status_code == 404
    assert response.json()["message"] == "Route not found"


def test_create_with_past_date_returns_400(client_db, organizer):
    past = (utcnow() - timedelta(days=1)).isoformat() + "Z"

    response = client_db.post(
        "/api/route-calls", json=valid_payload(dateRoute=past)
    )

    assert response.status_code == 400
    assert response.json()["success"] is False


@pytest.mark.parametrize(
    "points",
    [
        [SECONDARY_POINT],                                # zero PRIMARY
        [PRIMARY_POINT, PRIMARY_POINT],                   # two PRIMARY
        [PRIMARY_POINT, SECONDARY_POINT, SECONDARY_POINT],  # three points
    ],
    ids=["zero-primary", "two-primary", "three-points"],
)
def test_create_with_invalid_meeting_points_returns_400(
    client_db, organizer, points
):
    response = client_db.post(
        "/api/route-calls", json=valid_payload(meetingPoints=points)
    )

    assert response.status_code == 400
    assert response.json()["success"] is False


def test_create_without_auth_returns_401_envelope(client_db):
    response = client_db.post("/api/route-calls", json=valid_payload())

    assert response.status_code == 401
    assert response.json()["success"] is False


# --- GET /api/route-calls --------------------------------------------------


def test_upcoming_true_applies_the_two_hour_window(client_db, organizer, db_session):
    scheduled = make_route_call(
        db_session, organizer, RouteCallStatus.SCHEDULED, FUTURE
    )
    completed_old = make_route_call(
        db_session, organizer, RouteCallStatus.COMPLETED, utcnow() - timedelta(days=30)
    )
    cancelled_recent = make_route_call(  # 1h ago: still inside the 2h window
        db_session, organizer, RouteCallStatus.CANCELLED, utcnow() - timedelta(hours=1)
    )
    cancelled_stale = make_route_call(  # 3h ago: the window expired
        db_session, organizer, RouteCallStatus.CANCELLED, utcnow() - timedelta(hours=3)
    )

    response = client_db.get(
        "/api/route-calls",
        params={"upcoming": "true", "organizerId": organizer.id},
    )

    assert response.status_code == 200
    ids = [item["id"] for item in response.json()["data"]]
    assert scheduled.id in ids
    assert cancelled_recent.id in ids  # cancelled TODAY must stay visible
    assert completed_old.id not in ids
    assert cancelled_stale.id not in ids


def test_upcoming_false_returns_the_past_newest_first(client_db, organizer, db_session):
    older = make_route_call(
        db_session, organizer, RouteCallStatus.COMPLETED, utcnow() - timedelta(days=30)
    )
    newer = make_route_call(
        db_session, organizer, RouteCallStatus.CANCELLED, utcnow() - timedelta(hours=3)
    )

    response = client_db.get(
        "/api/route-calls",
        params={"upcoming": "false", "organizerId": organizer.id},
    )

    ids = [item["id"] for item in response.json()["data"]]
    assert ids == [newer.id, older.id]  # dateRoute desc


def test_invalid_month_returns_400_envelope(client_db):
    response = client_db.get("/api/route-calls", params={"month": "2026-13"})

    assert response.status_code == 400
    assert response.json()["success"] is False


def test_list_envelope_includes_pagination(client_db, organizer, db_session):
    make_route_call(db_session, organizer, RouteCallStatus.SCHEDULED, FUTURE)

    response = client_db.get(
        "/api/route-calls", params={"organizerId": organizer.id}
    )

    body = response.json()
    assert body["success"] is True
    pagination = body["pagination"]
    assert pagination["totalCount"] == 1
    assert pagination["page"] == 1
    assert pagination["hasNextPage"] is False


def test_detail_returns_confirmed_attendees_and_total_count(
    client_db, organizer, db_session, make_user
):
    route_call = make_route_call(
        db_session, organizer, RouteCallStatus.SCHEDULED, FUTURE
    )
    confirmed = make_user()
    make_attendance(db_session, route_call, confirmed)
    make_attendance(
        db_session, route_call, make_user(), status=AttendanceStatus.CANCELLED
    )

    response = client_db.get(f"/api/route-calls/{route_call.id}")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["organizer"]["id"] == organizer.id
    # D17: same slim slices as the list — no lastName on the organizer
    assert "lastName" not in data["organizer"]
    # The embedded list is CONFIRMED-only...
    assert [a["user"]["id"] for a in data["attendances"]] == [confirmed.id]
    # ...but _count counts EVERY status (Express quirk, pinned on purpose)
    assert data["_count"]["attendances"] == 2


def test_non_organizer_updating_a_completed_route_call_gets_403(
    client_db, as_user, db_session, make_user
):
    other = make_user()
    route_call = make_route_call(
        db_session, other, RouteCallStatus.COMPLETED, FUTURE
    )

    response = client_db.patch(
        f"/api/route-calls/{route_call.id}", json={"title": "Nope"}
    )

    # D18 pinned: permission BEFORE state (Express would have answered 400)
    assert response.status_code == 403
    assert response.json()["message"] == (
        "Only the organizer can update this route call"
    )


def test_delete_with_attendances_returns_400_even_if_cancelled(
    client_db, organizer, db_session, make_user
):
    route_call = make_route_call(
        db_session, organizer, RouteCallStatus.SCHEDULED, FUTURE
    )
    make_attendance(
        db_session, route_call, make_user(), status=AttendanceStatus.CANCELLED
    )

    response = client_db.delete(f"/api/route-calls/{route_call.id}")

    assert response.status_code == 400
    assert response.json()["message"] == (
        "Cannot delete a route call with attendances. Cancel it instead."
    )


def test_delete_cascades_over_the_meeting_points(client_db, organizer, db_session):
    created = client_db.post(
        "/api/route-calls",
        json=valid_payload(meetingPoints=[PRIMARY_POINT, SECONDARY_POINT]),
    ).json()["data"]
    points_of = (
        select(func.count())
        .select_from(MeetingPoint)
        .where(MeetingPoint.route_call_id == created["id"])
    )
    assert db_session.execute(points_of).scalar_one() == 2

    response = client_db.delete(f"/api/route-calls/{created['id']}")

    assert response.status_code == 200
    assert "data" not in response.json()  # exclude_unset, verified by test now
    assert db_session.execute(points_of).scalar_one() == 0  # PostgreSQL cascaded
    assert db_session.get(RouteCall, created["id"]) is None


# --- GET /api/route-calls/{id} ---------------------------------------------


def test_detail_of_unknown_route_call_returns_404(client_db):
    response = client_db.get(
        "/api/route-calls/00000000-0000-0000-0000-000000000000"
    )

    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert body["message"] == "Route call not found"


# --- PATCH /api/route-calls/{id} -------------------------------------------


def test_organizer_updates_their_scheduled_route_call(
    client_db, organizer, db_session
):
    route_call = make_route_call(
        db_session, organizer, RouteCallStatus.SCHEDULED, FUTURE
    )

    response = client_db.patch(
        f"/api/route-calls/{route_call.id}",
        json={"title": "Título nuevo", "paces": ["ROCA", "GUSANO"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "Route call updated successfully"
    assert body["data"]["title"] == "Título nuevo"
    assert body["data"]["paces"] == ["ROCA", "GUSANO"]
    # Partial update: the fields NOT sent kept their stored values
    assert route_call.image == "https://example.com/x.jpg"
    # The change is real: the row inside the savepoint bubble reflects it
    assert route_call.title == "Título nuevo"
    assert route_call.paces == [RoutePace.ROCA, RoutePace.GUSANO]


def test_non_organizer_cannot_update(client_db, as_user, db_session, make_user):
    route_call = make_route_call(
        db_session, make_user(), RouteCallStatus.SCHEDULED, FUTURE
    )

    response = client_db.patch(
        f"/api/route-calls/{route_call.id}", json={"title": "Nope"}
    )

    assert response.status_code == 403
    assert response.json()["message"] == (
        "Only the organizer can update this route call"
    )


@pytest.mark.parametrize(
    "status, message",
    [
        (RouteCallStatus.COMPLETED, "Cannot update a completed route call"),
        (RouteCallStatus.CANCELLED, "Cannot update a cancelled route call"),
        (RouteCallStatus.ONGOING, "Cannot update an ongoing route call"),
    ],
    ids=["completed", "cancelled", "ongoing"],
)
def test_update_blocked_states_return_400_with_exact_message(
    client_db, organizer, db_session, status, message
):
    route_call = make_route_call(db_session, organizer, status, FUTURE)

    response = client_db.patch(
        f"/api/route-calls/{route_call.id}", json={"title": "Nuevo"}
    )

    assert response.status_code == 400
    assert response.json()["message"] == message


def test_update_with_past_date_returns_400(client_db, organizer, db_session):
    route_call = make_route_call(
        db_session, organizer, RouteCallStatus.SCHEDULED, FUTURE
    )
    past = (utcnow() - timedelta(days=1)).isoformat() + "Z"

    response = client_db.patch(
        f"/api/route-calls/{route_call.id}", json={"dateRoute": past}
    )

    assert response.status_code == 400
    assert response.json()["success"] is False


# --- PATCH /api/route-calls/{id}/cancel ------------------------------------


def test_organizer_cancels_their_scheduled_route_call(
    client_db, organizer, db_session
):
    route_call = make_route_call(
        db_session, organizer, RouteCallStatus.SCHEDULED, FUTURE
    )

    response = client_db.patch(f"/api/route-calls/{route_call.id}/cancel")

    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "Route call cancelled successfully"
    assert body["data"]["status"] == "CANCELLED"
    # Soft state: the row survives, only its status changed
    assert route_call.status is RouteCallStatus.CANCELLED


def test_admin_cancels_someone_elses_route_call(
    client_db, as_admin, db_session, make_user
):
    route_call = make_route_call(
        db_session, make_user(), RouteCallStatus.SCHEDULED, FUTURE
    )

    response = client_db.patch(f"/api/route-calls/{route_call.id}/cancel")

    assert response.status_code == 200
    assert route_call.status is RouteCallStatus.CANCELLED


def test_cancel_an_already_cancelled_route_call_returns_400(
    client_db, organizer, db_session
):
    route_call = make_route_call(
        db_session, organizer, RouteCallStatus.CANCELLED, FUTURE
    )

    response = client_db.patch(f"/api/route-calls/{route_call.id}/cancel")

    assert response.status_code == 400
    assert response.json()["message"] == "Route call is already cancelled"


def test_cancel_a_completed_route_call_returns_400(
    client_db, organizer, db_session
):
    route_call = make_route_call(
        db_session, organizer, RouteCallStatus.COMPLETED, FUTURE
    )

    response = client_db.patch(f"/api/route-calls/{route_call.id}/cancel")

    assert response.status_code == 400
    assert response.json()["message"] == "Cannot cancel a completed route call"


@pytest.mark.parametrize("field", ["title", "dateRoute", "paces", "image"])
def test_update_with_explicit_null_on_required_field_returns_400(
    client_db, organizer, db_session, field
):
    route_call = make_route_call(
        db_session, organizer, RouteCallStatus.SCHEDULED, FUTURE
    )

    response = client_db.patch(
        f"/api/route-calls/{route_call.id}", json={field: None}
    )

    assert response.status_code == 400
    assert response.json()["success"] is False


# --- DELETE /api/route-calls/{id} ------------------------------------------


def test_admin_deletes_a_route_call_without_attendances(
    client_db, as_admin, db_session, make_user
):
    route_call = make_route_call(
        db_session, make_user(), RouteCallStatus.SCHEDULED, FUTURE
    )

    response = client_db.delete(f"/api/route-calls/{route_call.id}")

    assert response.status_code == 200
    assert response.json()["message"] == "Route call deleted successfully"
    # Hard delete: the row is gone from the bubble
    assert db_session.get(RouteCall, route_call.id) is None


def test_normal_user_cannot_delete_someone_elses_route_call(
    client_db, as_user, db_session, make_user
):
    route_call = make_route_call(
        db_session, make_user(), RouteCallStatus.SCHEDULED, FUTURE
    )

    response = client_db.delete(f"/api/route-calls/{route_call.id}")

    assert response.status_code == 403
    assert response.json()["message"] == (
        "Only the organizer or an admin can delete this route call"
    )