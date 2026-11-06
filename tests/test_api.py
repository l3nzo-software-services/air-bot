"""
Integration tests for FastAPI endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from cellsentinel.main import app
from cellsentinel.database import init_database
from cellsentinel.services.sms_parser import encode_sms_bracket_payload


@pytest.fixture(scope="module")
def client():
    init_database()
    with TestClient(app) as c:
        yield c


def test_health_check(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "HEALTHY"


def test_device_registration_and_get(client):
    imei_raw = "354123098765431"
    payload = {
        "imei_or_hash": imei_raw,
        "device_model": "OnePlus 12",
        "owner_name": "Test User",
        "owner_phone": "+919999988888",
        "owner_email": "test@example.com",
        "recovery_pin": "7777"
    }

    res = client.post("/api/v1/devices", json=payload)
    assert res.status_code == 201
    device_data = res.json()
    imei_hash = device_data["imei_hash"]

    # Verify GET
    get_res = client.get(f"/api/v1/devices/{imei_hash}")
    assert get_res.status_code == 200
    assert get_res.json()["device_model"] == "OnePlus 12"


def test_telemetry_rest_push(client):
    imei_hash = "abcdef112233445566778899aabbccddeeff00112233445566778899aabbccdd"
    telemetry_data = {
        "imei_hash": imei_hash,
        "mcc": 404,
        "mnc": 45,
        "lac": 1234,
        "cid": 5678,
        "signal_strength": -70.0,
        "carrier_name": "Bharti Airtel"
    }

    res = client.post("/api/v1/telemetry/push", json=telemetry_data)
    assert res.status_code == 201
    data = res.json()
    assert data["cid"] == 5678
    assert data["transport"] == "HTTPS"
    assert data["latitude"] > 0
    assert data["accuracy_radius"] > 0


def test_telemetry_sms_webhook(client):
    imei_hash = "112233445566778899aabbccddeeff00112233445566778899aabbccddeeff00"
    sms_bracket = encode_sms_bracket_payload(imei_hash, 404, 45, 1234, 5679, -85.0)

    # Twilio format webhook
    res = client.post(
        "/api/v1/telemetry/sms-webhook",
        data={"From": "+919811000000", "Body": sms_bracket}
    )
    assert res.status_code == 201
    data = res.json()
    assert data["transport"] == "SMS_OUT_OF_BAND"
    assert data["cid"] == 5679
    assert data["signal_strength"] == -85.0


def test_resolver_direct_lookup(client):
    res = client.post(
        "/api/v1/resolver/lookup",
        json={"mcc": 404, "mnc": 45, "lac": 1234, "cid": 5678, "signal_strength": -65.0}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["cid"] == 5678
    assert "Airtel" in data["carrier"]


def test_dashboard_summary(client):
    res = client.get("/api/v1/dashboard/summary")
    assert res.status_code == 200
    data = res.json()
    assert "total_devices" in data
    assert "lost_devices" in data
    assert "total_telemetry_pings" in data
