from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from src.core.config import settings

# One engine per application: manages the connection pool to Postgres.
# pool_pre_ping tests each pooled connection before use (Supabase closes idle ones).
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)

# Session factory: each request gets its own short-lived session.
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""


def get_db():
    """FastAPI dependency: yields a DB session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()