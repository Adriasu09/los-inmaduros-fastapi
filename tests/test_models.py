import pytest
from sqlalchemy import select

from src.core.database import SessionLocal
from src.core.models_registry import (
    Attendance,
    Favorite,
    MeetingPoint,
    Photo,
    Review,
    Route,
    RouteCall,
    User,
)

MODELS = [User, Route, RouteCall, MeetingPoint, Attendance, Review, Favorite, Photo]


@pytest.mark.parametrize("model", MODELS, ids=lambda m: m.__name__)
def test_model_mirrors_real_table(model):
    """Read-only SELECT touching every mapped column of the real table.

    If any column name in the model does not exist in the DB, this raises.
    """
    with SessionLocal() as db:
        db.execute(select(model).limit(1)).scalars().first()