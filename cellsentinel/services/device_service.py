"""
Device Registration and Authentication Service.
Handles owner-authorized device enrollment, cryptographic hashing of IMEIs,
and API key authentication for cellular telemetry submissions.
"""

import hashlib
import secrets
from typing import Tuple, Optional, List
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from cellsentinel.config import settings
from cellsentinel.models import Device
from cellsentinel.schemas import DeviceRegisterRequest


def hash_token(raw_token: str) -> str:
    """Hash API key token using cryptographic salt."""
    salted = f"{settings.API_TOKEN_SALT}:{raw_token}"
    return hashlib.sha256(salted.encode("utf-8")).hexdigest()


def register_device(db: Session, req: DeviceRegisterRequest) -> Tuple[Device, str]:
    """
    Register a new device.
    Verifies that the device IMEI hash is not already registered.
    Generates a private API key for authenticating telemetry submissions.
    """
    imei_hash = req.imei  # normalized to 64-char sha256 in schema validator

    # Check for duplicate
    existing = db.query(Device).filter(Device.imei_hash == imei_hash).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Device with IMEI hash '{imei_hash}' is already registered."
        )

    # Generate cryptographically secure API key
    raw_api_key = secrets.token_urlsafe(32)
    token_hash = hash_token(raw_api_key)

    device = Device(
        imei_hash=imei_hash,
        device_name=req.device_name.strip(),
        device_token_hash=token_hash,
        device_status="ACTIVE"
    )

    db.add(device)
    db.commit()
    db.refresh(device)

    return device, raw_api_key


def authenticate_device(db: Session, device_id_str: str, api_key: str) -> Device:
    """
    Verify device registration and credentials.
    Accepts either device numeric ID or 64-character IMEI hash.
    Raises 401 Unauthorized if invalid or 403 Forbidden if suspended.
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required: missing device API key."
        )

    device: Optional[Device] = None

    # Try lookup by integer ID
    if device_id_str.isdigit():
        device = db.query(Device).filter(Device.id == int(device_id_str)).first()

    # If not found, lookup by IMEI hash
    if not device:
        device = db.query(Device).filter(Device.imei_hash == device_id_str.strip().lower()).first()

    if not device:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed: device identifier not registered."
        )

    # Validate API key
    computed_hash = hash_token(api_key.strip())
    if computed_hash != device.device_token_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed: invalid device credentials."
        )

    # Check device lifecycle status
    if device.device_status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Device access denied: current status is '{device.device_status}'."
        )

    return device


def get_device_by_identifier(db: Session, identifier: str) -> Optional[Device]:
    """Retrieve device by primary ID, raw numeric IMEI, full IMEI hash, or prefix."""
    clean = identifier.strip().lower()

    if clean.isdigit():
        if len(clean) < 10:
            dev = db.query(Device).filter(Device.id == int(clean)).first()
            if dev:
                return dev
        if len(clean) >= 14:
            raw_hash = hashlib.sha256(clean.encode("utf-8")).hexdigest().lower()
            dev = db.query(Device).filter(Device.imei_hash == raw_hash).first()
            if dev:
                return dev

    # Exact IMEI hash match
    dev = db.query(Device).filter(Device.imei_hash == clean).first()
    if dev:
        return dev

    # Prefix search (at least 8 chars)
    if len(clean) >= 8:
        dev = db.query(Device).filter(Device.imei_hash.startswith(clean)).first()
        if dev:
            return dev

    return None


def list_devices(db: Session) -> List[Device]:
    """List all registered devices ordered by last seen timestamp."""
    return db.query(Device).order_by(Device.last_seen_timestamp.desc().nullslast()).all()
