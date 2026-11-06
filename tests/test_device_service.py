"""
Unit tests for Device Identity & Hardware Registry service.
"""

import hashlib
import pytest
from cellsentinel.database import init_database
from cellsentinel.models import DeviceRegisterRequest, DeviceState
from cellsentinel.services import device_service


@pytest.fixture(autouse=True)
def setup_db():
    init_database()


def test_device_registration_with_raw_imei():
    raw_imei = "861234567890123"
    req = DeviceRegisterRequest(
        imei_or_hash=raw_imei,
        device_model="Test Terminal X",
        owner_name="Alice Sentinel",
        owner_phone="+1234567890",
        owner_email="alice@sentinel.org",
        recovery_pin="5555"
    )

    device = device_service.register_device(req)
    # Verify raw IMEI was automatically converted to SHA-256 hash
    expected_hash = hashlib.sha256(raw_imei.encode("utf-8")).hexdigest().lower()
    assert device.imei_hash == expected_hash
    assert device.state == DeviceState.SECURE
    assert device.device_model == "Test Terminal X"

    # Verify retrieval by hash
    retrieved = device_service.get_device_by_hash(expected_hash)
    assert retrieved is not None
    assert retrieved.owner_name == "Alice Sentinel"


def test_device_state_transitions():
    raw_imei = "990001234567890"
    req = DeviceRegisterRequest(
        imei_or_hash=raw_imei,
        device_model="Test Terminal Y",
        owner_name="Bob Sentinel",
        owner_phone="+1987654321",
        owner_email="bob@sentinel.org",
        recovery_pin="4321"
    )
    dev = device_service.register_device(req)

    # Transition to LOST with valid PIN
    updated_lost = device_service.update_device_state(
        imei_hash=dev.imei_hash,
        new_state=DeviceState.LOST,
        pin="4321",
        reason="Reported stolen"
    )
    assert updated_lost.state == DeviceState.LOST

    # Verify invalid PIN is rejected
    with pytest.raises(PermissionError):
        device_service.update_device_state(
            imei_hash=dev.imei_hash,
            new_state=DeviceState.RECOVERED,
            pin="wrong-pin"
        )

    # Transition to RECOVERED with correct PIN
    updated_rec = device_service.update_device_state(
        imei_hash=dev.imei_hash,
        new_state=DeviceState.RECOVERED,
        pin="4321"
    )
    assert updated_rec.state == DeviceState.RECOVERED
