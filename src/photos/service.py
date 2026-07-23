from sqlalchemy.orm import Session

from src.common.storage import upload_image, validate_image
from src.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from src.photos.models import Photo, PhotoContext, PhotoStatus
from src.photos.schemas import PhotoOut
from src.route_calls.models import RouteCall

_COVER_FOLDER = "route-calls/covers"


def upload_photo(
    db: Session,
    user_id: str,
    file_bytes: bytes,
    content_type: str,
    ext: str,
    *,
    context: PhotoContext,
    route_id: str | None,
    route_call_id: str | None,
    caption: str | None,
) -> PhotoOut:
    """Upload a photo. Only the ROUTE_CALL_COVER context is implemented for now;
    the galleries and moderation are deferred with the rest of the photos module."""
    # 1. Validate the file (type + size) before touching the DB or Storage.
    validate_image(content_type, len(file_bytes))

    # 2. Only the cover context is available today (galleries/moderation deferred).
    if context is not PhotoContext.ROUTE_CALL_COVER:
        raise BadRequestError("Photo context not available yet")

    # 3. A cover needs its route call (Express' Zod refinement, 400 not 404).
    if route_call_id is None:
        raise BadRequestError(
            "routeCallId is required for ROUTE_CALL_COVER and ROUTE_CALL_GALLERY contexts"
        )

    # 4. The route call must exist.
    route_call = db.get(RouteCall, route_call_id)
    if route_call is None:
        raise NotFoundError("Route call not found")

    # 5. Only its organizer may set the cover (fine-grained permission in the service).
    if route_call.organizer_id != user_id:
        raise ForbiddenError("Only the organizer can upload a cover photo")

    # 6. Upload to Storage and record the photo (born ACTIVE, D2).
    image_url = upload_image(file_bytes, content_type, ext, _COVER_FOLDER)
    photo = Photo(
        context=PhotoContext.ROUTE_CALL_COVER,
        route_id=None,
        route_call_id=route_call_id,
        user_id=user_id,
        image_url=image_url,
        caption=caption,
        status=PhotoStatus.ACTIVE,
    )
    db.add(photo)

    # 7. Cross-update: the route call's own cover field is what the frontend renders
    #    on the card and the detail — this is what makes the photo actually show up.
    route_call.image = image_url

    db.commit()
    return PhotoOut.model_validate(photo)
