import secrets
import time

from supabase import Client, create_client

from src.core.config import settings
from src.core.exceptions import BadRequestError

# The public bucket that serves photo URLs directly (mirror of Express).
BUCKET_NAME = "photos"

# Allowed image types and size cap, identical to the Express upload middleware
# and storage service (same 5MB limit, same MIME whitelist, same messages).
ALLOWED_CONTENT_TYPES = frozenset(
    {"image/jpeg", "image/jpg", "image/png", "image/gif", "image/webp"}
)
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB in bytes

# Lazily-built singleton: the client is only needed for a real upload, so tests
# (which monkeypatch upload_image) never construct it and never need credentials.
_client: Client | None = None


def _get_client() -> Client:
    """Return the Supabase client, building it on first use with the service role
    key (D6: server-side only, full Storage access, bypasses RLS)."""
    global _client
    if _client is None:
        if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
            raise RuntimeError(
                "Supabase Storage is not configured "
                "(SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY missing)"
            )
        _client = create_client(
            settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY
        )
    return _client


def validate_image(content_type: str, size: int) -> None:
    """Reject anything that is not an allowed image type or exceeds 5MB (400)."""
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise BadRequestError(
            "Invalid file type. Only JPEG, PNG, GIF, and WebP images are allowed."
        )
    if size > MAX_FILE_SIZE:
        raise BadRequestError("File too large. Maximum file size is 5MB.")


def upload_image(file_bytes: bytes, content_type: str, ext: str, folder: str) -> str:
    """Upload image bytes to `photos/{folder}/{timestamp}-{random}.{ext}` and
    return the public URL. Not upserted: every upload gets a unique name."""
    file_name = f"{int(time.time() * 1000)}-{secrets.token_hex(4)}.{ext}"
    file_path = f"{folder}/{file_name}"

    bucket = _get_client().storage.from_(BUCKET_NAME)
    bucket.upload(
        file_path,
        file_bytes,
        {"content-type": content_type, "upsert": "false"},
    )
    return bucket.get_public_url(file_path)
