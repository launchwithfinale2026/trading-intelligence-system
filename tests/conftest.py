from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.database import get_db
from app.database.models import Base


def _new_sqlite_engine():
    # StaticPool keeps a single underlying connection alive for the engine's
    # lifetime — without it, sqlite:///:memory: hands out a fresh, empty
    # database on every new connection and "no such table" errors follow.
    return create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """A fresh, isolated in-memory SQLite database per test.

    Uses Base.metadata.create_all directly rather than Alembic — this keeps
    tests fast and hermetic. Alembic migrations are exercised separately
    (applied to the real dev/prod database), not re-verified per test.
    """
    engine = _new_sqlite_engine()
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """A TestClient wired to its own isolated in-memory database.

    Every request within a test shares one session (FastAPI caches
    Depends(get_db) per request), and each test gets a fresh database.
    """
    from app.main import app

    engine = _new_sqlite_engine()
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db() -> Generator[Session, None, None]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
