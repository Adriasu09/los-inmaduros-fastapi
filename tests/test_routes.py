"""Routes module tests — docs/gherkin/routes.feature scenarios (T-14)."""

import re
from statistics import mean

import pytest
from sqlalchemy import select

from src.photos.models import Photo, PhotoStatus
from src.reviews.models import Review
from src.routes.models import Route
from tests.conftest import fake_user

# Exactly Date.prototype.toISOString(): 3-digit milliseconds + Z
UTC_Z_FORMAT = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")


@pytest.fixture()
def route(db_session) -> Route:
    """Any real route to hang synthetic data from (read-only anchor)."""
    return db_session.scalars(select(Route).order_by(Route.name)).first()


def add_review(db, route_id: str, rating: int) -> Review:
    """Synthetic review inside the savepoint; one fresh user per review
    (the reviews_userId_routeId_key unique allows one review per user/route)."""
    user = fake_user()
    db.add(user)
    review = Review(route_id=route_id, user_id=user.id, rating=rating)
    db.add(review)
    db.flush()
    return review


def add_photo(db, route_id: str, status: PhotoStatus) -> Photo:
    user = fake_user()
    db.add(user)
    photo = Photo(
        route_id=route_id, user_id=user.id,
        image_url=f"http://test.local/{status.value.lower()}.jpg", status=status,
    )
    db.add(photo)
    db.flush()
    return photo


# Scenario: List all predefined routes
def test_catalogue_lists_routes_ordered_with_rating_and_counts(client):
    res = client.get("/api/routes")
    body = res.json()

    assert res.status_code == 200
    assert body["success"] is True
    assert body["count"] == len(body["data"])
    names = [r["name"] for r in body["data"]]
    assert names == sorted(names)
    for item in body["data"]:
        assert isinstance(item["averageRating"], (int, float))
        assert set(item["_count"]) == {"reviews", "favorites", "routeCalls", "photos"}


# Scenario: Predefined routes are available after seeding
def test_the_17_seeded_routes_are_present(client):
    body = client.get("/api/routes").json()

    assert body["count"] == 17


# Scenario: Get a route detail by slug
def test_detail_by_slug_includes_every_contract_block(client_db, route):
    body = client_db.get(f"/api/routes/{route.slug}").json()
    data = body["data"]

    assert body["success"] is True
    for key in (
        "description", "level", "mapEmbedUrl", "gpxFileUrl",
        "averageRating", "_count", "reviews", "photos", "reviewsPagination",
    ):
        assert key in data, f"missing block: {key}"


# Scenario: Get a non-existent route
def test_unknown_slug_returns_404_envelope(client):
    res = client.get("/api/routes/este-slug-no-existe")

    assert res.status_code == 404
    assert res.json() == {"success": False, "message": "Route not found"}


# Scenario: Paginate the reviews of a route
def test_reviews_pagination_returns_the_requested_page(client_db, db_session, route):
    before = client_db.get(f"/api/routes/{route.slug}").json()
    existing = before["data"]["reviewsPagination"]["totalCount"]
    for _ in range(25):
        add_review(db_session, route.id, rating=3)

    body = client_db.get(
        f"/api/routes/{route.slug}?reviewsPage=2&reviewsLimit=10"
    ).json()
    block = body["data"]["reviewsPagination"]

    assert len(body["data"]["reviews"]) == 10
    assert block["page"] == 2
    assert block["limit"] == 10
    assert block["totalCount"] == existing + 25
    assert block["hasPreviousPage"] is True
    assert block["hasNextPage"] is (2 < -(-(existing + 25) // 10))  # ceil


# Scenario: Only active photos are shown in the route detail
def test_detail_only_returns_active_photos(client_db, db_session, route):
    active = add_photo(db_session, route.id, PhotoStatus.ACTIVE)
    rejected = add_photo(db_session, route.id, PhotoStatus.REJECTED)

    photos = client_db.get(f"/api/routes/{route.slug}").json()["data"]["photos"]
    returned_ids = {p["id"] for p in photos}

    assert active.id in returned_ids
    assert rejected.id not in returned_ids
    assert all(p["status"] == "ACTIVE" for p in photos)


# Scenario: Average rating reflects the route reviews
def test_average_rating_is_the_rounded_mean_of_ratings(client_db, db_session, route):
    existing = db_session.scalars(
        select(Review.rating).where(Review.route_id == route.id)
    ).all()
    for rating in (2, 5):
        add_review(db_session, route.id, rating)
    expected = round(mean([*existing, 2, 5]), 1)

    body = client_db.get(f"/api/routes/{route.slug}").json()

    assert body["data"]["averageRating"] == expected


# Extra DoD assert: dates leave the API in JS toISOString() format
def test_dates_are_serialized_with_milliseconds_and_z(client):
    item = client.get("/api/routes").json()["data"][0]

    assert UTC_Z_FORMAT.match(item["createdAt"]), item["createdAt"]
    assert UTC_Z_FORMAT.match(item["updatedAt"]), item["updatedAt"]