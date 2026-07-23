from sqlalchemy import select

from src.photos.models import Photo, PhotoStatus
from src.route_calls.models import RouteCall, RouteCallStatus
from tests.conftest import FAKE_STORAGE_URL
from tests.test_route_calls import FUTURE, make_route_call, organizer  # noqa: F401

# A minimal valid JPEG upload part: (filename, bytes, content_type).
JPEG = ("cover.jpg", b"\xff\xd8\xff\xe0fake-jpeg-bytes", "image/jpeg")


def _upload(client, *, file=JPEG, context="ROUTE_CALL_COVER", route_call_id=None, **extra):
    """POST /api/photos as multipart, mirroring what the frontend sends."""
    data = {"context": context, **extra}
    if route_call_id is not None:
        data["routeCallId"] = route_call_id
    return client.post("/api/photos", files={"image": file}, data=data)


def test_organizer_upload_returns_201_and_updates_route_call_image(
    client_db, organizer, db_session
):
    route_call = make_route_call(
        db_session, organizer, RouteCallStatus.SCHEDULED, FUTURE
    )

    response = _upload(client_db, route_call_id=route_call.id)

    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Photo uploaded successfully"
    data = body["data"]
    assert data["context"] == "ROUTE_CALL_COVER"
    assert data["status"] == "ACTIVE"
    assert data["routeCallId"] == route_call.id
    assert data["routeId"] is None
    assert data["imageUrl"] == FAKE_STORAGE_URL

    # Cross-update: the Photo row exists AND the route call's cover now points to it.
    db_session.expire_all()
    photo = db_session.execute(
        select(Photo).where(Photo.route_call_id == route_call.id)
    ).scalar_one()
    assert photo.image_url == FAKE_STORAGE_URL
    assert photo.status is PhotoStatus.ACTIVE
    assert photo.user_id == organizer.id

    refreshed = db_session.get(RouteCall, route_call.id)
    assert refreshed.image == FAKE_STORAGE_URL


def test_non_organizer_returns_403(client_db, as_user, make_user, db_session):
    other_organizer = make_user()
    route_call = make_route_call(
        db_session, other_organizer, RouteCallStatus.SCHEDULED, FUTURE
    )

    response = _upload(client_db, route_call_id=route_call.id)

    assert response.status_code == 403
    assert response.json()["message"] == "Only the organizer can upload a cover photo"


def test_unknown_route_call_returns_404(client_db, organizer):
    response = _upload(
        client_db, route_call_id="00000000-0000-0000-0000-000000000000"
    )

    assert response.status_code == 404
    assert response.json()["message"] == "Route call not found"


def test_missing_route_call_id_returns_400(client_db, organizer):
    response = _upload(client_db)  # ROUTE_CALL_COVER without a routeCallId

    assert response.status_code == 400
    assert response.json()["message"] == (
        "routeCallId is required for ROUTE_CALL_COVER and ROUTE_CALL_GALLERY contexts"
    )


def test_invalid_file_type_returns_400(client_db, organizer, db_session):
    route_call = make_route_call(
        db_session, organizer, RouteCallStatus.SCHEDULED, FUTURE
    )

    response = _upload(
        client_db,
        route_call_id=route_call.id,
        file=("notes.txt", b"not an image", "text/plain"),
    )

    assert response.status_code == 400
    assert response.json()["message"] == (
        "Invalid file type. Only JPEG, PNG, GIF, and WebP images are allowed."
    )


def test_file_too_large_returns_400(client_db, organizer, db_session):
    route_call = make_route_call(
        db_session, organizer, RouteCallStatus.SCHEDULED, FUTURE
    )
    too_big = ("big.jpg", b"x" * (5 * 1024 * 1024 + 1), "image/jpeg")

    response = _upload(client_db, route_call_id=route_call.id, file=too_big)

    assert response.status_code == 400
    assert response.json()["message"] == "File too large. Maximum file size is 5MB."


def test_gallery_context_not_available_returns_400(client_db, organizer, db_session):
    route_call = make_route_call(
        db_session, organizer, RouteCallStatus.SCHEDULED, FUTURE
    )

    response = _upload(
        client_db, route_call_id=route_call.id, context="ROUTE_CALL_GALLERY"
    )

    assert response.status_code == 400
    assert response.json()["message"] == "Photo context not available yet"
