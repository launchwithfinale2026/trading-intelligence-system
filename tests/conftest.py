from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database.models import Base


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """A fresh, isolated in-memory SQLite database per test.

    Uses Base.metadata.create_all directly rather than Alembic — this keeps
    tests fast and hermetic. Alembic migrations are exercised separately
    (applied to the real dev/prod database), not re-verified per test.
    """
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
