from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from sqlalchemy.orm import Session

from src.auth.deps import get_current_user
from src.auth.models import User
from src.common.rate_limit import CREATION_LIMIT, CREATION_LIMIT_MESSAGE, limiter
from src.core.database import get_db
from src.core.schemas import ApiResponse
from src.photos import service
from src.photos.models import PhotoContext
from src.photos.schemas import PhotoOut

router = APIRouter(prefix="/api/photos", tags=["Photos"])

# Content type -> extension used to name the stored object. The service validates
# the content type first, so an unlisted type never reaches Storage.
_EXT_BY_CONTENT_TYPE = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/gif": "gif",
    "image/webp": "webp",
}


@router.post(
    "",
    status_code=201,
    response_model=ApiResponse[PhotoOut],
    response_model_exclude_unset=True,
)
@limiter.limit(CREATION_LIMIT, error_message=CREATION_LIMIT_MESSAGE)
def upload_photo(
    request: Request,
    image: UploadFile = File(...),
    context: PhotoContext = Form(...),
    route_id: str | None = Form(None, alias="routeId"),
    route_call_id: str | None = Form(None, alias="routeCallId"),
    caption: str | None = Form(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    file_bytes = image.file.read()
    content_type = image.content_type or ""
    ext = _EXT_BY_CONTENT_TYPE.get(content_type, "bin")

    photo = service.upload_photo(
        db,
        user.id,
        file_bytes,
        content_type,
        ext,
        context=context,
        route_id=route_id,
        route_call_id=route_call_id,
        caption=caption,
    )
    return ApiResponse[PhotoOut](
        success=True, data=photo, message="Photo uploaded successfully"
    )
