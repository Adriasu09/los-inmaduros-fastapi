"""Imports every model so they all register on Base.metadata.

Import THIS module (not each models.py) wherever the full model
registry is needed: Alembic's env.py, tests, etc.
"""
from src.attendances.models import Attendance
from src.auth.models import User
from src.favorites.models import Favorite
from src.photos.models import Photo
from src.reviews.models import Review
from src.route_calls.models import MeetingPoint, RouteCall
from src.routes.models import Route

__all__ = [
    "Attendance",
    "User",
    "Favorite",
    "Photo",
    "Review",
    "MeetingPoint",
    "RouteCall",
    "Route",
]