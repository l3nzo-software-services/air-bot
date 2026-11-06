"""
Unit and integration tests for Cell-Tower Triangulation & Geolocation Resolver.
"""

import asyncio
import pytest
from cellsentinel.database import init_database
from cellsentinel.services.resolver import resolve_cell_tower


@pytest.fixture(autouse=True)
def setup_db():
    init_database()


def test_resolve_prompt_sample_tower():
    # Prompt explicit sample: MCC 404, MNC 45 (Airtel), LAC 1234, CID 5678
    res = asyncio.run(
        resolve_cell_tower(
            mcc=404,
            mnc=45,
            lac=1234,
            cid=5678,
            signal_strength=-75.0,
            radio_type="LTE"
        )
    )

    assert res.mcc == 404
    assert res.mnc == 45
    assert res.lac == 1234
    assert res.cid == 5678
    # Resolves to Delhi Connaught Place
    assert 28.5 < res.latitude < 28.7
    assert 77.1 < res.longitude < 77.3
    assert "Airtel" in res.carrier
    assert res.accuracy_radius > 0.0


def test_resolve_fallback_offline_synthesizer():
    # Unknown arbitrary cell tower in Germany (MCC 262, MNC 01)
    res = asyncio.run(
        resolve_cell_tower(
            mcc=262,
            mnc=1,
            lac=9999,
            cid=88888,
            signal_strength=-95.0
        )
    )

    assert res.mcc == 262
    assert res.mnc == 1
    # Check that coordinate is situated in Central Europe / Germany bounding area (~52 Lat, ~13 Lon)
    assert 47.0 < res.latitude < 55.0
    assert 5.0 < res.longitude < 16.0
    assert res.source in ("RF_PATH_LOSS_SYNTHESIZER", "TELECOM_CACHE")
    assert res.accuracy_radius >= 120.0
