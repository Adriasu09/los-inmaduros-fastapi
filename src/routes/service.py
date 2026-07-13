from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from src.common.pagination import build_pagination
from src.core.exceptions import NotFoundError
from src.favorites.models import Favorite
from src.photos.models import Photo, PhotoStatus
from src.reviews.models import Review
from src.route_calls.models import RouteCall
from src.routes.models import Route
from src.routes.schemas import (
    PhotoOut,
    ReviewOut,
    RouteCounts,
    RouteDetailOut,
    RouteListItem,
)

_ROUTE_COLUMNS = (
    "id", "name", "slug", "image", "approximate_distance", "description",
    "gpx_file_url", "map_embed_url", "level", "created_at", "updated_at",
)


def _route_columns(route: Route) -> dict:
    return {name: getattr(route, name) for name in _ROUTE_COLUMNS}


def _round_rating(average) -> float:
    """Parity with Express: Number(avg.toFixed(1)) with `|| 0` when no reviews."""
    return round(float(average), 1) if average is not None else 0


def _avg_rating_subquery():
    """Scalar subquery: the average travels INSIDE the main query (no N+1)."""
    return (
        select(func.avg(Review.rating))
        .where(Review.route_id == Route.id)
        .scalar_subquery()
    )


def _count_subquery(fk_column):
    """Scalar subquery counting rows of a related table for the outer Route."""
    return select(func.count()).where(fk_column == Route.id).scalar_subquery()


def _route_with_aggregates_query():
    """Route + rating average + the 4 counters, all in ONE SELECT."""
    return select(
        Route,
        _avg_rating_subquery().label("average_rating"),
        _count_subquery(Review.route_id).label("reviews"),
        _count_subquery(Favorite.route_id).label("favorites"),
        _count_subquery(RouteCall.route_id).label("route_calls"),
        _count_subquery(Photo.route_id).label("photos"),
    )


def list_routes(db: Session) -> list[RouteListItem]:
    """Catalogue: every route ordered by name, with rating and counts."""
    rows = db.execute(_route_with_aggregates_query().order_by(Route.name.asc())).all()
    return [
        RouteListItem(
            **_route_columns(route),
            average_rating=_round_rating(average),
            counts=RouteCounts(
                reviews=reviews, favorites=favorites,
                route_calls=route_calls, photos=photos,
            ),
        )
        for route, average, reviews, favorites, route_calls, photos in rows
    ]


def get_route_by_slug(
    db: Session,
    slug: str,
    reviews_page: int = 1,
    reviews_limit: int = 20,
    photos_limit: int = 20,
) -> RouteDetailOut:
    """Detail: the route + a page of reviews (with author) + ACTIVE photos."""
    row = db.execute(
        _route_with_aggregates_query().where(Route.slug == slug)
    ).first()
    if row is None:
        raise NotFoundError("Route not found")
    route, average, reviews_count, favorites, route_calls, photos_count = row

    reviews = (
        db.execute(
            select(Review)
            .options(joinedload(Review.user))  # author in the SAME query
            .where(Review.route_id == route.id)
            .order_by(Review.created_at.desc())
            .offset((reviews_page - 1) * reviews_limit)
            .limit(reviews_limit)
        )
        .scalars()
        .all()
    )

    photos = (
        db.execute(
            select(Photo)
            .where(Photo.route_id == route.id, Photo.status == PhotoStatus.ACTIVE)
            .order_by(Photo.created_at.desc())
            .limit(photos_limit)
        )
        .scalars()
        .all()
    )

    return RouteDetailOut(
        **_route_columns(route),
        average_rating=_round_rating(average),
        counts=RouteCounts(
            reviews=reviews_count, favorites=favorites,
            route_calls=route_calls, photos=photos_count,
        ),
        reviews=[ReviewOut.model_validate(r) for r in reviews],
        photos=[PhotoOut.model_validate(p) for p in photos],
        reviews_pagination=build_pagination(reviews_page, reviews_limit, reviews_count),
    )