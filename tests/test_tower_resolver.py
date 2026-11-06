"""
Automated tests for Cell Tower Triangulation & Geolocation Resolver Engine.
Verifies resolution priority, caching, API mocking, and strict non-fabrication rules.
"""

import asyncio
from datetime import datetime, timezone
import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from cellsentinel.database import Base
from cellsentinel.models import CellTowerCache
from cellsentinel.services.tower_resolver import resolve_cell_tower, get_carrier_name

# Test DB
test_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


def test_carrier_name_resolution():
    """Verify carrier identification from MCC/MNC combinations."""
    assert "Airtel" in get_carrier_name(404, 45)
    assert "Jio" in get_carrier_name(404, 20)
    assert "AT&T" in get_carrier_name(310, 410)
    assert "EE" in get_carrier_name(234, 30)


def test_local_tower_cache_lookup():
    """Priority 1: Verify resolver retrieves pre-existing cache entry."""
    with TestingSessionLocal() as db:
        # Pre-populate cache
        cache = CellTowerCache(
            mcc=404,
            mnc=45,
            lac=1234,
            cell_id=7777,
            latitude=28.6139,
            longitude=77.2090,
            accuracy_radius=600.0,
            source="CACHE_TEST",
            last_updated=datetime.now(timezone.utc)
        )
        db.add(cache)
        db.commit()

        resolved = asyncio.run(resolve_cell_tower(db, 404, 45, 1234, 7777))
        assert resolved.location_source == "CACHE"
        assert resolved.latitude == 28.6139
        assert resolved.longitude == 77.2090
        assert resolved.accuracy_radius == 600.0


def test_verified_local_reference_fallback():
    """Priority 3: Verify resolver uses verified local reference catalog."""
    with TestingSessionLocal() as db:
        # Query verified Delhi Connaught Place tower: 404, 45, 1234, 56789
        resolved = asyncio.run(resolve_cell_tower(db, 404, 45, 1234, 56789))
        assert resolved.location_source in ("LOCAL_VERIFIED", "CACHE")
        assert 28.5 < resolved.latitude < 28.7
        assert 77.1 < resolved.longitude < 77.3
        assert resolved.accuracy_radius == 750.0


@patch("cellsentinel.services.tower_resolver._query_opencellid_api")
def test_opencellid_api_mock_integration(mock_query):
    """Priority 2: Verify OpenCellID API integration and cache persistence."""
    mock_query.return_value = {
        "latitude": 40.7128,
        "longitude": -74.0060,
        "accuracy_radius": 550.0,
        "source": "OPENCELLID"
    }

    with TestingSessionLocal() as db:
        resolved = asyncio.run(resolve_cell_tower(db, 310, 260, 5000, 12345))
        assert resolved.location_source == "OPENCELLID"
        assert resolved.latitude == 40.7128
        assert resolved.longitude == -74.0060
        assert resolved.accuracy_radius == 550.0

        # Verify entry was persisted into SQLite cache
        cached = (
            db.query(CellTowerCache)
            .filter(CellTowerCache.cell_id == 12345)
            .first()
        )
        assert cached is not None
        assert cached.source == "OPENCELLID"


@patch("cellsentinel.services.tower_resolver._query_opencellid_api")
def test_api_failure_fallback_to_verified_catalog(mock_query):
    """Verify that when OpenCellID fails (None), resolver falls back gracefully."""
    mock_query.return_value = None  # API timeout / failure

    with TestingSessionLocal() as db:
        # Use known verified reference tower (Barakhamba: 404, 45, 1234, 5678)
        resolved = asyncio.run(resolve_cell_tower(db, 404, 45, 1234, 5678))
        assert resolved.location_source in ("LOCAL_VERIFIED", "CACHE")
        assert resolved.latitude is not None
        assert resolved.accuracy_radius == 680.0


def test_unknown_tower_unresolved_handling():
    """
    Priority 4 & Strict Directives:
    Verify that an unknown cell tower produces explicit UNRESOLVED status:
    - Never generates fake coordinates (latitude and longitude must be None)
    - Never invents accuracy radius (accuracy_radius must be None)
    - Clearly marks location_source as UNRESOLVED
    """
    with TestingSessionLocal() as db:
        resolved = asyncio.run(resolve_cell_tower(db, 999, 99, 9999, 999999))
        assert resolved.location_source == "UNRESOLVED"
        assert resolved.latitude is None
        assert resolved.longitude is None
        assert resolved.accuracy_radius is None
        assert resolved.cell_id == 999999
