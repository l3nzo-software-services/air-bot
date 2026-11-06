"""
Integration tests for the standalone CellSentinel app.py.
"""

import asyncio
import pytest
import sqlite3
from fastapi.testclient import TestClient
from app import app, init_db, resolve_cell_tower, DB_FILE


@pytest.fixture(scope="module")
def client():
    init_db()
    with TestClient(app) as c:
        yield c


def test_database_initialization():
    init_db()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Verify tables exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='devices';")
    assert cursor.fetchone() is not None

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='telemetry_history';")
    assert cursor.fetchone() is not None
    conn.close()


def test_opencellid_triangulation_resolver():
    # Test reference cell tower: MCC 404, MNC 45, LAC 1234, Cell_ID 56789
    res = asyncio.run(resolve_cell_tower(404, 45, 1234, 56789))
    assert 28.5 < res["latitude"] < 28.7
    assert 77.1 < res["longitude"] < 77.3
    assert res["accuracy_radius"] > 0
    assert "Airtel" in res["carrier_name"]


def test_telemetry_ingest_and_search(client):
    # Ingest live telemetry payload
    payload = {
        "imei": "358941098765432",
        "device_name": "Google Pixel 8 Pro",
        "mcc": 404,
        "mnc": 45,
        "lac": 1234,
        "cell_id": 56789
    }

    res = client.post("/api/telemetry", json=payload)
    assert res.status_code == 201
    data = res.json()["data"]
    assert data["imei"] == "358941098765432"
    assert data["mcc"] == 404
    assert data["mnc"] == 45
    assert data["cell_id"] == 56789
    assert data["latitude"] > 0
    assert data["longitude"] > 0

    # Search device by IMEI
    search_res = client.get(f"/api/devices/{payload['imei']}")
    assert search_res.status_code == 200
    device = search_res.json()
    assert device["device_name"] == "Google Pixel 8 Pro"
    assert device["cell_id"] == 56789
    assert "carrier_name" in device
    assert len(device["history"]) >= 1


def test_health_check(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ONLINE"


def test_dashboard_html_rendering(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "CellSentinel" in res.text
    assert "leaflet" in res.text
    assert "imeiSearchInput" in res.text
