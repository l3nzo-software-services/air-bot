"""
Automated tests for Device Registration, Cryptographic Hashing, and Authentication.
"""

import hashlib
import pytest
from cellsentinel.models import Device
from tests.conftest import TestingSessionLocal


def test_database_initialization():
    """Verify database tables and indexes are created properly."""
    from tests.conftest import test_engine
    with test_engine.connect() as conn:
        tables = conn.dialect.get_table_names(conn)
        assert "devices" in tables
        assert "telemetry" in tables
        assert "cell_tower_cache" in tables


def test_device_registration_with_raw_imei(client):
    """Verify raw 15-digit IMEI is hashed to 64-char SHA-256 for privacy."""
    raw_imei = "358941098765432"
    expected_hash = hashlib.sha256(raw_imei.encode()).hexdigest().lower()

    payload = {
        "imei": raw_imei,
        "device_name": "Samsung Galaxy S24 Ultra"
    }

    res = client.post("/api/devices", json=payload)
    assert res.status_code == 201
    data = res.json()

    assert data["imei_hash"] == expected_hash
    assert data["device_name"] == "Samsung Galaxy S24 Ultra"
    assert data["device_status"] == "ACTIVE"
    assert "api_key" in data
    assert len(data["api_key"]) > 20


def test_duplicate_device_rejection(client):
    """Verify duplicate device registration is rejected with 409 Conflict."""
    payload = {
        "imei": "862145041234567",
        "device_name": "Google Pixel 8"
    }

    # First registration
    res1 = client.post("/api/devices", json=payload)
    assert res1.status_code == 201

    # Second registration with same IMEI
    res2 = client.post("/api/devices", json=payload)
    assert res2.status_code == 409
    assert "already registered" in res2.json()["detail"]


def test_device_authentication(client):
    """Verify device authentication with valid and invalid tokens."""
    # Register device
    res = client.post("/api/devices", json={"imei": "112233445566778", "device_name": "OnePlus 12"})
    assert res.status_code == 201
    reg_data = res.json()
    valid_key = reg_data["api_key"]
    device_id = reg_data["id"]

    # Valid telemetry packet with valid token
    telemetry_payload = {
        "device_id": str(device_id),
        "mcc": 404,
        "mnc": 45,
        "lac": 1234,
        "cell_id": 56789,
        "signal_strength": -75.0
    }

    auth_res = client.post(
        "/api/telemetry",
        headers={"X-Device-Token": valid_key},
        json=telemetry_payload
    )
    assert auth_res.status_code == 201
    assert auth_res.json()["success"] is True

    # Telemetry packet with invalid token
    bad_res = client.post(
        "/api/telemetry",
        headers={"X-Device-Token": "invalid-token-12345"},
        json=telemetry_payload
    )
    assert bad_res.status_code == 401
    assert "invalid device credentials" in bad_res.json()["detail"].lower()


def test_suspended_device_rejection(client):
    """Verify suspended or inactive device cannot submit telemetry."""
    # Register device
    res = client.post("/api/devices", json={"imei": "998877665544332", "device_name": "Test Terminal"})
    reg_data = res.json()
    valid_key = reg_data["api_key"]
    device_id = reg_data["id"]

    # Suspend device in DB
    with TestingSessionLocal() as db:
        dev = db.query(Device).filter(Device.id == device_id).first()
        dev.device_status = "SUSPENDED"
        db.commit()

    telemetry_payload = {
        "device_id": str(device_id),
        "mcc": 404,
        "mnc": 45,
        "lac": 1234,
        "cell_id": 56789
    }

    sus_res = client.post(
        "/api/telemetry",
        headers={"X-Device-Token": valid_key},
        json=telemetry_payload
    )
    assert sus_res.status_code == 403
    assert "access denied" in sus_res.json()["detail"].lower()


def test_hardware_derived_key_authentication(client):
    """Verify hardware-derived key authenticates successfully even if issued token is lost/reset."""
    from cellsentinel.services.device_service import derive_hardware_key

    raw_imei = "861952072527237"
    reg_res = client.post("/api/devices", json={
        "imei": raw_imei,
        "device_name": "realme 14x pro"
    })
    assert reg_res.status_code == 201
    dev_data = reg_res.json()
    imei_hash = dev_data["imei_hash"]

    # Compute hardware-derived key (as done by phone after factory wipe)
    hw_key = derive_hardware_key(imei_hash)

    # Ingest telemetry using hardware-derived key without using issued api_key
    telem_res = client.post(
        "/api/telemetry",
        headers={"X-Device-Token": hw_key},
        json={
            "device_id": imei_hash,
            "mcc": 404,
            "mnc": 45,
            "lac": 8520,
            "cell_id": 41201
        }
    )
    assert telem_res.status_code == 201
    assert telem_res.json()["success"] is True

