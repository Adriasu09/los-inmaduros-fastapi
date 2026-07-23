from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.auth.deps import get_current_user, require_admin
from src.auth.models import User, UserRole
from src.core.config import settings

from src.common.rate_limit import limiter  # noqa: E402
from src.core.database import engine, get_db  # noqa: E402
from src.main import app  # noqa: E402
import src.photos.service as _photos_service  # noqa: E402

settings.SCHEDULER_ENABLED = False

settings.TELEGRAM_BOT_TOKEN = None
settings.TELEGRAM_CHAT_ID = None

limiter.enabled = False

FAKE_STORAGE_URL = "https://storage.test.local/fake-cover.jpg"
_photos_service.upload_image = lambda *args, **kwargs: FAKE_STORAGE_URL


@pytest.fixture()
def client():
    """HTTP client against the real app, running in memory."""
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def db_session():
    """Session inside an outer transaction that is ALWAYS rolled back: zero residue."""
    connection = engine.connect()
    transaction = connection.begin()
    # create_savepoint: the code under test may call commit() freely — each commit
    # becomes a SAVEPOINT inside our outer transaction, never a real COMMIT.
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


def fake_user(role: UserRole = UserRole.USER) -> User:
    """In-memory User, never persisted: identity for permission tests."""
    return User(
        id=str(uuid4()),
        clerk_id=f"user_{uuid4().hex[:12]}",
        email=f"{uuid4().hex[:8]}@test.local",
        name="Test",
        last_name="User",
        role=role,
    )


@pytest.fixture()
def as_user():
    """The app sees a regular USER as the authenticated identity (no Clerk, no DB)."""
    user = fake_user(UserRole.USER)
    app.dependency_overrides[get_current_user] = lambda: user
    yield user
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture()
def as_admin():
    """The app sees an ADMIN as the authenticated identity."""
    user = fake_user(UserRole.ADMIN)
    app.dependency_overrides[get_current_user] = lambda: user
    yield user
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture()
def client_db(db_session):
    """Client whose endpoints use the transactional bubble session (zero residue)."""
    def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


# --- Test-only routes: exercise the real auth dependencies (no real module yet) ---
test_router = APIRouter(prefix="/_test")


@test_router.get("/protected")
def protected_probe(user: Annotated[User, Depends(get_current_user)]):
    return {"id": user.id, "role": user.role.value}


@test_router.get("/admin-only")
def admin_probe(user: Annotated[User, Depends(require_admin)]):
    return {"id": user.id}


app.include_router(test_router)


@pytest.fixture(scope="session", autouse=True)
def users_table_residue_guard():
    """DoD guard: the whole suite must leave the users table count untouched."""
    with engine.connect() as conn:
        before = conn.execute(text("SELECT COUNT(*) FROM users")).scalar()
    yield
    with engine.connect() as conn:
        after = conn.execute(text("SELECT COUNT(*) FROM users")).scalar()
    assert after == before, f"Tests left residue in users: {before} -> {after}"


@pytest.fixture()
def make_user(db_session):
    """Factory: persist a synthetic user inside the savepoint bubble."""
    def _make(role: UserRole = UserRole.USER) -> User:
        user = fake_user(role)
        db_session.add(user)
        db_session.commit()  # savepoint: evaporates on rollback
        return user
    return _make