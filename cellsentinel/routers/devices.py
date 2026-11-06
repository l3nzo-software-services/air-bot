"""
Device Identity & Registry API Router.
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, status

from cellsentinel.models import (
    DeviceRegisterRequest,
    DeviceResponse,
    DeviceState,
    DeviceStateUpdateRequest,
    TelemetryRecord,
    IncidentEvent
)
from cellsentinel.services import device_service, telemetry_service

router = APIRouter(prefix="/api/v1/devices", tags=["Devices"])


@router.post(
    "",
    response_model=DeviceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new device hardware identity"
)
def register_device_endpoint(req: DeviceRegisterRequest):
    """
    Secure registration of hardware identifiers:
    - Normalizes raw 15-digit IMEI or preserves SHA-256 hash.
    - Saves device model, owner emergency contacts, and salted recovery PIN.
    - Sets initial status to SECURE.
    """
    try:
        return device_service.register_device(req)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "",
    response_model=List[DeviceResponse],
    summary="List registered devices"
)
def list_devices_endpoint(
    state: Optional[DeviceState] = Query(None, description="Filter by device state"),
    q: Optional[str] = Query(None, description="Search by IMEI hash, model, owner name, or phone")
):
    """Retrieve list of registered devices matching filter criteria."""
    return device_service.list_devices(state_filter=state, query=q)


@router.get(
    "/{imei_hash}",
    response_model=DeviceResponse,
    summary="Get device details by IMEI hash"
)
def get_device_endpoint(imei_hash: str):
    """Retrieve complete device hardware and status record."""
    device = device_service.get_device_by_hash(imei_hash)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device with identifier '{imei_hash}' not found."
        )
    return device


@router.patch(
    "/{imei_hash}/state",
    response_model=DeviceResponse,
    summary="Update device state (SECURE, LOST, RECOVERED)"
)
def update_state_endpoint(imei_hash: str, req: DeviceStateUpdateRequest):
    """
    Transition device lifecycle state.
    Triggers emergency incident notifications when marked LOST or RECOVERED.
    """
    try:
        return device_service.update_device_state(
            imei_hash=imei_hash,
            new_state=req.state,
            pin=req.recovery_pin,
            reason=req.reason
        )
    except PermissionError as pe:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))


@router.get(
    "/{imei_hash}/trajectory",
    response_model=List[TelemetryRecord],
    summary="Get device trajectory breadcrumbs for map"
)
def get_trajectory_endpoint(
    imei_hash: str,
    limit: int = Query(200, ge=1, le=1000)
):
    """Retrieve historical cell tower transition trajectory for Leaflet map polyline."""
    return telemetry_service.get_device_trajectory(imei_hash, limit=limit)


@router.get(
    "/{imei_hash}/events",
    response_model=List[IncidentEvent],
    summary="Get incident audit timeline"
)
def get_timeline_endpoint(imei_hash: str):
    """Retrieve chronological audit events (handovers, state changes, SMS alerts)."""
    return device_service.get_device_timeline_events(imei_hash)

