import logging
from datetime import datetime, timedelta, timezone
from typing import cast

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import CursorResult, update
from sqlalchemy.orm import Session

from src.core.database import SessionLocal, utcnow
from src.route_calls.models import RouteCall, RouteCallStatus

logger = logging.getLogger(__name__)

# A route call is considered "ongoing" for 2 hours after its start (parity with
# Express' route-call-scheduler.service.ts).
ROUTE_CALL_DURATION = timedelta(hours=2)


def run_status_transitions(db: Session) -> tuple[int, int]:
    """Move every OVERDUE route call to its next status, in two batch UPDATEs."""
    now = utcnow()

    # db.execute() is typed as the generic Result, but a DML UPDATE returns a
    # CursorResult (which carries .rowcount). cast documents that runtime fact.
    ongoing = cast(
        CursorResult,
        db.execute(
            update(RouteCall)
            .where(
                RouteCall.status == RouteCallStatus.SCHEDULED,
                RouteCall.date_route <= now,
            )
            .values(status=RouteCallStatus.ONGOING, updated_at=now)
        ),
    )
    completed = cast(
        CursorResult,
        db.execute(
            update(RouteCall)
            .where(
                RouteCall.status == RouteCallStatus.ONGOING,
                RouteCall.date_route <= now - ROUTE_CALL_DURATION,
            )
            .values(status=RouteCallStatus.COMPLETED, updated_at=now)
        ),
    )
    db.commit()
    return ongoing.rowcount, completed.rowcount


def _job() -> None:
    """What the scheduler thread runs: its own session + error isolation so a
    failure NEVER crashes the app or the scheduler loop."""
    db = SessionLocal()
    try:
        to_ongoing, to_completed = run_status_transitions(db)
        if to_ongoing or to_completed:
            logger.info(
                "Route-call transitions: %s -> ONGOING, %s -> COMPLETED",
                to_ongoing,
                to_completed,
            )
    except Exception:
        db.rollback()
        logger.exception("Route-call status transition failed")
    finally:
        db.close()


def start_scheduler() -> BackgroundScheduler:
    """Run the catch-up job immediately and then every minute (parity with Express).

    `next_run_time=now` gives the immediate startup catch-up; `coalesce` +
    `misfire_grace_time` mean a tick delayed by a wake-up still runs (just once).
    """
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        _job,
        trigger="interval",
        minutes=1,
        next_run_time=datetime.now(timezone.utc),
        id="route_call_status_transitions",
        coalesce=True,
        max_instances=1,
        misfire_grace_time=300,
    )
    scheduler.start()
    logger.info("Route-call status scheduler started (every minute).")
    return scheduler
