from datetime import timedelta

from src.common.scheduler import run_status_transitions
from src.core.database import utcnow
from src.route_calls.models import RouteCallStatus

# Reuse the synthetic-data helpers from the route-calls suite.
from tests.test_route_calls import make_route_call, organizer  # noqa: F401


def test_scheduler_transitions_only_the_overdue_ones(db_session, organizer):
    """SCHEDULED->ONGOING at start; ONGOING->COMPLETED after 2h; catch-up jumps a
    long-overdue SCHEDULED straight to COMPLETED in one run."""
    now = utcnow()
    just_started = make_route_call(
        db_session, organizer, RouteCallStatus.SCHEDULED, now - timedelta(minutes=5)
    )
    still_future = make_route_call(
        db_session, organizer, RouteCallStatus.SCHEDULED, now + timedelta(days=1)
    )
    ongoing_recent = make_route_call(
        db_session, organizer, RouteCallStatus.ONGOING, now - timedelta(hours=1)
    )
    ongoing_old = make_route_call(
        db_session, organizer, RouteCallStatus.ONGOING, now - timedelta(hours=3)
    )
    scheduled_long_ago = make_route_call(
        db_session, organizer, RouteCallStatus.SCHEDULED, now - timedelta(hours=3)
    )

    run_status_transitions(db_session)

    for rc in (just_started, still_future, ongoing_recent, ongoing_old, scheduled_long_ago):
        db_session.refresh(rc)

    assert just_started.status is RouteCallStatus.ONGOING  # past start
    assert still_future.status is RouteCallStatus.SCHEDULED  # untouched
    assert ongoing_recent.status is RouteCallStatus.ONGOING  # < 2h
    assert ongoing_old.status is RouteCallStatus.COMPLETED  # > 2h
    assert scheduled_long_ago.status is RouteCallStatus.COMPLETED  # catch-up in one run
