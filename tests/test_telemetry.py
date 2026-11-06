"""
Automated tests for Telemetry Ingestion, History, and Dashboard APIs.
"""

import pytest


@pytest.fixture
def registered_device(client):
    """Helper fixture providing an authenticated device and its API key."""
    res = client.post("/api/devices", json={
        "imei": "358941098765432",
        "device_name": "Google Pixel 8 Pro"
    })
    return res.json()


def test_valid_authenticated_telemetry_ingestion(client, registered_device):
    """Verify authenticated device can submit valid telemetry."""
    device_id = registered_device["id"]
    api_key = registered_device["api_key"]

    payload = {
        "device_id": str(device_id),
        "mcc": 404,
        "mnc": 45,
        "lac": 1234,
        "cell_id": 56789,
        "signal_strength": -75.0
    }

    res = client.post(
        "/api/telemetry",
        headers={"X-Device-Token": api_key},
        json=payload
    )

    assert res.status_code == 201
    data = res.json()
    assert data["success"] is True
    assert data["tower"]["cell_id"] == 56789
    assert data["tower"]["mcc"] == 404
    assert data["tower"]["mnc"] == 45
    assert data["tower"]["latitude"] is not None
    assert data["tower"]["longitude"] is not None
    assert data["tower"]["accuracy_radius"] is not None
    assert "Airtel" in data["tower"]["carrier_name"]


def test_unauthenticated_telemetry_rejection(client, registered_device):
    """Verify telemetry without authorization token is rejected with 401."""
    device_id = registered_device["id"]
    payload = {
        "device_id": str(device_id),
        "mcc": 404,
        "mnc": 45,
        "lac": 1234,
        "cell_id": 56789
    }

    res = client.post("/api/telemetry", json=payload)
    assert res.status_code == 401
    assert "missing device authentication token" in res.json()["detail"].lower()


def test_invalid_telemetry_parameter_validation(client, registered_device):
    """Verify telemetry with invalid parameters (e.g. invalid MCC, negative LAC) is rejected with 422."""
    api_key = registered_device["api_key"]

    # Invalid MCC (0 is out of bounds for MCC: 1-999)
    bad_payload = {
        "device_id": str(registered_device["id"]),
        "mcc": 0,
        "mnc": 45,
        "lac": 1234,
        "cell_id": 56789
    }

    res = client.post(
        "/api/telemetry",
        headers={"X-Device-Token": api_key},
        json=bad_payload
    )
    assert res.status_code == 422


def test_telemetry_history_retrieval(client, registered_device):
    """Verify chronological telemetry history retrieval."""
    device_id = registered_device["id"]
    api_key = registered_device["api_key"]

    # Submit two distinct tower telemetry hops
    t1 = {"device_id": str(device_id), "mcc": 404, "mnc": 45, "lac": 1234, "cell_id": 56789, "signal_strength": -70.0}
    t2 = {"device_id": str(device_id), "mcc": 404, "mnc": 45, "lac": 1234, "cell_id": 5678, "signal_strength": -85.0}

    client.post("/api/telemetry", headers={"X-Device-Token": api_key}, json=t1)
    client.post("/api/telemetry", headers={"X-Device-Token": api_key}, json=t2)

    history_res = client.get(f"/api/telemetry/{device_id}/history")
    assert history_res.status_code == 200
    history = history_res.json()
    assert len(history) == 2
    # Verify latest hop appears first
    assert history[0]["cell_id"] == 5678
    assert history[1]["cell_id"] == 56789


def test_dashboard_search_and_stats(client, registered_device):
    """Verify dashboard search endpoint and aggregate statistics."""
    imei_hash = registered_device["imei_hash"]

    # Search by full IMEI hash
    s1 = client.get(f"/api/dashboard/search?q={imei_hash}")
    assert s1.status_code == 200
    results = s1.json()
    assert len(results) == 1
    assert results[0]["imei_hash"] == imei_hash

    # Search by prefix
    s2 = client.get(f"/api/dashboard/search?q={imei_hash[:12]}")
    assert s2.status_code == 200
    assert len(s2.json()) == 1

    # Verify operational stats
    stats_res = client.get("/api/dashboard/stats")
    assert stats_res.status_code == 200
    stats = stats_res.json()
    assert stats["total_devices"] >= 1
    assert stats["active_devices"] >= 1


def test_dashboard_html_view(client):
    """Verify root HTML dashboard serves successfully."""
    res = client.get("/")
    assert res.status_code == 200
    assert "AIR BOT" in res.text
    assert "TELECOM NOTICE" in res.text
    assert "leaflet" in res.text


def test_realtime_dashboard_sse_stream(client):
    """Verify Server-Sent Events (SSE) streaming endpoint connectivity."""
    with client.stream("GET", "/api/dashboard/events") as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        # Read the initial connection ping
        lines = []
        for line in response.iter_lines():
            if line:
                lines.append(line)
            if len(lines) >= 2:
                break
        assert any("ping" in l for l in lines)


def test_sms_out_of_band_telemetry_ingestion(client, registered_device):
    """Verify offline SMS telemetry payload decoding and tower resolution."""
    raw_imei = "358941098765432"
    sms_body = f"LOC:{raw_imei}:404:45:1234:56789:-68"

    res = client.post(
        "/api/telemetry/sms-webhook",
        json={
            "sender": "+919876543210",
            "message": sms_body
        }
    )

    assert res.status_code == 201
    data = res.json()
    assert data["success"] is True
    assert data["tower"]["cell_id"] == 56789
    assert data["tower"]["latitude"] is not None
    assert data["tower"]["longitude"] is not None
    assert data["tower"]["accuracy_radius"] == 750.0

