"""
Pydantic schemas and serialization models for CellSentinel.
"""

from datetime import datetime
from typing import Optional, List
import re
import hashlib
from pydantic import BaseModel, Field, field_validator, ConfigDict


class DeviceRegisterRequest(BaseModel):
    """Payload to register an owner-authorized device."""
    imei: str = Field(
        ...,
        description="Either raw 14-16 digit IMEI or 64-character SHA-256 hash."
    )
    device_name: str = Field(..., min_length=2, max_length=120)

    @field_validator("imei")
    @classmethod
    def validate_and_normalize_imei(cls, v: str) -> str:
        clean = v.strip()
        # If already a 64-character hex hash
        if re.fullmatch(r"^[a-fA-F0-9]{64}$", clean):
            return clean.lower()
        # If numeric IMEI (14 to 16 digits)
        digits = re.sub(r"\D", "", clean)
        if 14 <= len(digits) <= 16:
            return hashlib.sha256(digits.encode("utf-8")).hexdigest().lower()
        # Fallback SHA-256 for test identifier strings
        return hashlib.sha256(clean.encode("utf-8")).hexdigest().lower()


class DeviceRegisterResponse(BaseModel):
    """Response returned upon successful device registration."""
    id: int
    imei_hash: str
    device_name: str
    device_status: str
    registration_timestamp: datetime
    api_key: str = Field(
        ...,
        description="Private API key for the device. Store securely; not retrievable again."
    )

    model_config = ConfigDict(from_attributes=True)


class TelemetryIngestRequest(BaseModel):
    """Expected telemetry packet submitted by an authorized client device."""
    device_id: str = Field(..., description="Device ID (integer as string) or 64-char IMEI hash")
    mcc: int = Field(..., ge=1, le=999, description="Mobile Country Code (e.g. 404 for India, 310 for USA)")
    mnc: int = Field(..., ge=0, le=999, description="Mobile Network Code (e.g. 45 for Airtel)")
    lac: int = Field(..., ge=0, le=65535, description="Location Area Code")
    cell_id: int = Field(..., ge=0, le=268435455, description="Cell Tower ID")
    signal_strength: Optional[float] = Field(
        default=None,
        ge=-140.0,
        le=-20.0,
        description="Received signal strength indicator (RSSI / RSRP) in dBm"
    )


class TowerLocation(BaseModel):
    """Cell tower coordinates and coverage envelope."""
    mcc: int
    mnc: int
    lac: int
    cell_id: int
    carrier_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    accuracy_radius: Optional[float] = None
    location_source: str = Field(..., description="'CACHE', 'OPENCELLID', 'LOCAL_VERIFIED', or 'UNRESOLVED'")


class SmsWebhookRequest(BaseModel):
    """Payload for out-of-band SMS telemetry ingestion."""
    sender: Optional[str] = Field(default=None, description="Incoming phone number")
    message: str = Field(..., description="Raw SMS text e.g. LOC:<IMEI_OR_HASH>:<MCC>:<MNC>:<LAC>:<CID>:<RSSI>")


class TelemetryIngestResponse(BaseModel):
    """Structured response returned after telemetry ingestion."""
    success: bool
    device_id: str
    tower: TowerLocation
    timestamp: datetime
    message: str


class TelemetryHistoryItem(BaseModel):
    """Historical telemetry record entry."""
    id: int
    mcc: int
    mnc: int
    lac: int
    cell_id: int
    carrier_name: Optional[str] = None
    signal_strength: Optional[float] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    accuracy_radius: Optional[float] = None
    location_source: str
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)


class DeviceDetailResponse(BaseModel):
    """Device profile with latest resolved tower and status."""
    id: int
    imei_hash: str
    device_name: str
    device_status: str
    registration_timestamp: datetime
    last_seen_timestamp: Optional[datetime] = None
    latest_tower: Optional[TowerLocation] = None
    latest_signal_strength: Optional[float] = None
    telemetry_count: int = 0

    model_config = ConfigDict(from_attributes=True)
