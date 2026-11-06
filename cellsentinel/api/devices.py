"""
Device Management API Router.
Handles owner-authorized device registration, device discovery, and status queries.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from cellsentinel.database import get_db
from cellsentinel.schemas import (
    DeviceRegisterRequest,
    DeviceRegisterResponse,
    DeviceDetailResponse,
    TowerLocation
)
from cellsentinel.services import device_service
from cellsentinel.services.tower_resolver import get_carrier_name

router = APIRouter(prefix="/api/devices", tags=["Devices"])


@router.post(
    "",
    response_model=DeviceRegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register an authorized device"
)
def register_device_endpoint(
    req: DeviceRegisterRequest,
    db: Session = Depends(get_db)
):
    """
    Owner-authorized device registration:
    - Normalizes and cryptographically hashes the hardware IMEI with SHA-256
    - Rejects duplicate IMEI registrations
    - Issues a private device API key for authenticating telemetry submissions
    """
    device, raw_api_key = device_service.register_device(db, req)
    return DeviceRegisterResponse(
        id=device.id,
        imei_hash=device.imei_hash,
        device_name=device.device_name,
        device_status=device.device_status,
        registration_timestamp=device.registration_timestamp,
        api_key=raw_api_key
    )


@router.get(
    "",
    response_model=List[DeviceDetailResponse],
    summary="List registered devices"
)
def list_devices_endpoint(db: Session = Depends(get_db)):
    """List all registered devices with their latest status and location summaries."""
    devices = device_service.list_devices(db)
    results = []

    for dev in devices:
        latest_telemetry = dev.telemetry_records[0] if dev.telemetry_records else None
        latest_tower = None
        latest_rssi = None

        if latest_telemetry:
            latest_rssi = latest_telemetry.signal_strength
            latest_tower = TowerLocation(
                mcc=latest_telemetry.mcc,
                mnc=latest_telemetry.mnc,
                lac=latest_telemetry.lac,
                cell_id=latest_telemetry.cell_id,
                carrier_name=get_carrier_name(latest_telemetry.mcc, latest_telemetry.mnc),
                latitude=latest_telemetry.latitude,
                longitude=latest_telemetry.longitude,
                accuracy_radius=latest_telemetry.accuracy_radius,
                location_source=latest_telemetry.location_source
            )

        results.append(
            DeviceDetailResponse(
                id=dev.id,
                imei_hash=dev.imei_hash,
                device_name=dev.device_name,
                device_status=dev.device_status,
                registration_timestamp=dev.registration_timestamp,
                last_seen_timestamp=dev.last_seen_timestamp,
                latest_tower=latest_tower,
                latest_signal_strength=latest_rssi,
                telemetry_count=len(dev.telemetry_records)
            )
        )
    return results


@router.get(
    "/{identifier}",
    response_model=DeviceDetailResponse,
    summary="Get device details by ID or IMEI hash"
)
def get_device_endpoint(identifier: str, db: Session = Depends(get_db)):
    """Retrieve device metadata, latest tower location, and status."""
    dev = device_service.get_device_by_identifier(db, identifier)
    if not dev:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device identifier '{identifier}' not found."
        )

    latest_telemetry = dev.telemetry_records[0] if dev.telemetry_records else None
    latest_tower = None
    latest_rssi = None

    if latest_telemetry:
        latest_rssi = latest_telemetry.signal_strength
        latest_tower = TowerLocation(
            mcc=latest_telemetry.mcc,
            mnc=latest_telemetry.mnc,
            lac=latest_telemetry.lac,
            cell_id=latest_telemetry.cell_id,
            carrier_name=get_carrier_name(latest_telemetry.mcc, latest_telemetry.mnc),
            latitude=latest_telemetry.latitude,
            longitude=latest_telemetry.longitude,
            accuracy_radius=latest_telemetry.accuracy_radius,
            location_source=latest_telemetry.location_source
        )

    return DeviceDetailResponse(
        id=dev.id,
        imei_hash=dev.imei_hash,
        device_name=dev.device_name,
        device_status=dev.device_status,
        registration_timestamp=dev.registration_timestamp,
        last_seen_timestamp=dev.last_seen_timestamp,
        latest_tower=latest_tower,
        latest_signal_strength=latest_rssi,
        telemetry_count=len(dev.telemetry_records)
    )

