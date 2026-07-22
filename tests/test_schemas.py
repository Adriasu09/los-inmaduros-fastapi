from datetime import datetime, timezone
from types import SimpleNamespace

from src.core.schemas import CamelModel, UTCDateTime, UTCDateTimeIn


class StampedSchema(CamelModel):
    """Ad-hoc schema to pin the UTCDateTime output format."""

    created_at: UTCDateTime


class RatedSchema(CamelModel):
    """Ad-hoc schema to pin the automatic snake -> camel aliasing."""

    average_rating: float


class ScheduledSchema(CamelModel):
    """Ad-hoc schema to pin the UTCDateTimeIn normalization on input."""

    date_route: UTCDateTimeIn


def test_utc_datetime_serializes_with_milliseconds_and_z():
    schema = StampedSchema(created_at=datetime(2026, 1, 1, 12, 0, 0))

    assert schema.model_dump()["created_at"] == "2026-01-01T12:00:00.000Z"


def test_utc_datetime_serializes_aware_without_double_offset():
    # An AWARE datetime (e.g. from a model_dump round-trip that re-parsed a "...Z"
    # string) must NOT produce "...000+00:00Z" — JS would read it as Invalid Date.
    schema = StampedSchema(created_at=datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc))

    assert schema.model_dump()["created_at"] == "2026-01-01T12:00:00.000Z"


def test_utc_datetime_truncates_microseconds_to_milliseconds():
    # DB timestamps carry microseconds; the contract format has exactly 3 digits
    schema = StampedSchema(created_at=datetime(2026, 1, 1, 12, 0, 0, 123456))

    assert schema.model_dump()["created_at"] == "2026-01-01T12:00:00.123Z"


def test_camel_model_serializes_snake_case_as_camel_case():
    schema = RatedSchema(average_rating=4.5)

    assert schema.model_dump(by_alias=True) == {"averageRating": 4.5}


def test_camel_model_accepts_both_python_name_and_alias():
    # populate_by_name=True: the Python name and the alias are both valid inputs
    by_name = RatedSchema(average_rating=4.5)
    by_alias = RatedSchema.model_validate({"averageRating": 4.5})

    assert by_name.average_rating == by_alias.average_rating == 4.5


def test_camel_model_builds_from_orm_like_attributes():
    # from_attributes=True: reads .average_rating off any object, like a
    # SQLAlchemy model instance (SimpleNamespace stands in for one here)
    orm_like = SimpleNamespace(average_rating=3.7)

    schema = RatedSchema.model_validate(orm_like)

    assert schema.average_rating == 3.7


def test_incoming_utc_z_becomes_naive_utc():
    # "Z" means the client sent UTC; we store it naive, same clock reading
    schema = ScheduledSchema.model_validate({"dateRoute": "2026-02-15T10:00:00Z"})

    assert schema.date_route == datetime(2026, 2, 15, 10, 0, 0)
    assert schema.date_route.tzinfo is None


def test_incoming_offset_is_converted_to_utc_then_made_naive():
    # +02:00 (Madrid) at 10:00 is 08:00 UTC: the instant must be preserved
    schema = ScheduledSchema.model_validate({"dateRoute": "2026-02-15T10:00:00+02:00"})

    assert schema.date_route == datetime(2026, 2, 15, 8, 0, 0)
    assert schema.date_route.tzinfo is None