from datetime import timedelta

import pytest
from sqlalchemy import select

from src.core.database import utcnow
from src.route_calls.models import RouteCall, RouteCallStatus, RoutePace
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