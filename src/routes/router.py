from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.core.schemas import ApiResponse
from src.routes import service
from src.routes.schemas import RouteDetailOut, RouteListItem

router = APIRouter(prefix="/api/routes", tags=["Routes"])


@router.get("", response_model=ApiResponse[list[RouteListItem]], response_model_exclude_unset=True)
def list_routes(db: Session = Depends(get_db)):
    routes = service.list_routes(db)
    return ApiResponse[list[RouteListItem]](success=True, data=routes, count=len(routes))


@router.get("/{slug}", response_model=ApiResponse[RouteDetailOut], response_model_exclude_unset=True)
def get_route_by_slug(
    slug: str,
    db: Session = Depends(get_db),
    reviews_page: int = Query(1, ge=1, alias="reviewsPage"),
    reviews_limit: int = Query(20, ge=1, le=100, alias="reviewsLimit"),
    photos_limit: int = Query(20, ge=1, le=100, alias="photosLimit"),
):
    route = service.get_route_by_slug(db, slug, reviews_page, reviews_limit, photos_limit)
    return ApiResponse[RouteDetailOut](success=True, data=route)