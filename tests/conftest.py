"""
Pytest configuration and shared fixtures for CellSentinel test suite.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from cellsentinel.database import Base, get_db
from cellsentinel.main import app

# Shared in-memory SQLite engine with StaticPool so all threads share state
test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@pytest.fixture(scope="session", autouse=True)
def setup_app_overrides():
    """Configure dependency override for FastAPI app across all test modules."""
    Base.metadata.create_all(bind=test_engine)
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(autouse=True)
def clean_tables_between_tests():
    """Ensure clean database tables for each test function."""
    Base.metadata.create_all(bind=test_engine)
    yield
    # Clean table data
    with TestingSessionLocal() as session:
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()


@pytest.fixture
def client():
    """TestClient fixture."""
    with TestClient(app) as c:
        yield c
