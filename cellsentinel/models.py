"""
Pydantic schemas and data models for CellSentinel.
"""

from datetime import datetime
from enum import Enum
import hashlib
import re
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator


class DeviceState(str, Enum):
    """Lifecycle states of registered devices."""
    SECURE = "SECURE"
    LOST = "LOST"
    RECOVERED = "RECOVERED"


class TransportType(str, Enum):
    """Telemetry data transport mechanisms."""
    HTTPS = "HTTPS"
    SMS_OUT_OF_BAND = "SMS_OUT_OF_BAND"


class SimStatus(str, Enum):
    """SIM card verification status."""
    ACTIVE = "ACTIVE"
    CHANGED = "CHANGED"
    ROAMING = "ROAMING"
    UNSPECIFIED = "UNSPECIFIED"


class DeviceRegisterRequest(BaseModel):
    """Payload to register a new device hardware identity."""
    imei_or_hash: str = Field(
        ...,
        description="Either raw 15-digit IMEI or precomputed 64-character SHA-256 hash."
    )
    device_model: str = Field(..., min_length=2, max_length=100)
    owner_name: str = Field(..., min_length=2, max_length=100)
    owner_phone: str = Field(..., min_length=7, max_length=25)
    owner_email: str = Field(..., min_length=5, max_length=120)
    recovery_pin: Optional[str] = Field(default="1234", min_length=4, max_length=16)
    sim_imsi: Optional[str] = Field(default=None, description="Optional baseline IMSI / SIM ID")

    @field_validator("imei_or_hash")
    @classmethod
    def validate_and_normalize_imei(cls, v: str) -> str:
        clean = v.strip()
        # If it's already a 64-char hex hash
        if re.fullmatch(r"^[a-fA-F0-9]{64}$", clean):
            return clean.lower()
        # If it's a 14-16 digit raw IMEI, hash it with SHA-256
        digits_only = re.sub(r"\D", "", clean)
        if 14 <= len(digits_only) <= 16:
            return hashlib.sha256(digits_only.encode("utf-8")).hexdigest().lower()
        # If shorter custom alphanumeric token for test, SHA-256 hash it
        return hashlib.sha256(clean.encode("utf-8")).hexdigest().lower()


class DeviceStateUpdateRequest(BaseModel):
    """Payload to transition device state."""
    state: DeviceState
    recovery_pin: Optional[str] = None
    reason: Optional[str] = Field(default=None, max_length=255)


class CellTowerTelemetry(BaseModel):
    """Incoming cellular tower broadcast telemetry packet."""
    imei_hash: str = Field(
        ...,
        description="64-char IMEI SHA-256 hash, or raw IMEI which will be hashed automatically."
    )
    mcc: int = Field(..., ge=1, le=999, description="Mobile Country Code (e.g. 404 for India, 310 for USA)")
    mnc: int = Field(..., ge=0, le=999, description="Mobile Network Code (e.g. 45 for Airtel, 20 for Jio)")
    lac: int = Field(..., ge=0, le=65535, description="Location Area Code / TAC")
    cid: int = Field(..., ge=0, le=268435455, description="Cell Tower ID")
    signal_strength: float = Field(
        ...,
        ge=-140.0,
        le=-20.0,
        description="RSSI / RSRP in dBm (e.g. -75.0)"
    )
    carrier_name: Optional[str] = Field(default=None, max_length=100)
    radio_type: Optional[str] = Field(default="LTE", description="GSM, UMTS, LTE, NR5G")
    timing_advance: Optional[int] = Field(default=None, ge=0, le=1282)
    sim_status: Optional[str] = Field(default="ACTIVE")
    sim_imsi: Optional[str] = Field(default=None)
    raw_payload: Optional[str] = Field(default=None)

    @field_validator("imei_hash")
    @classmethod
    def normalize_imei_hash(cls, v: str) -> str:
        clean = v.strip()
        if re.fullmatch(r"^[a-fA-F0-9]{64}$", clean):
            return clean.lower()
        return hashlib.sha256(clean.encode("utf-8")).hexdigest().lower()


class SMSWebhookPayload(BaseModel):
    """Flexible schema parsing SMS gateway webhooks (Twilio, Telnyx, or raw compact hex)."""
    From: Optional[str] = Field(default=None, description="Sender phone number (Twilio standard)")
    Body: Optional[str] = Field(default=None, description="SMS message text containing compact payload")
    sender: Optional[str] = Field(default=None, description="Generic gateway sender")
    message: Optional[str] = Field(default=None, description="Generic gateway message body")
    payload: Optional[str] = Field(default=None, description="Direct payload parameter")
    hex_payload: Optional[str] = Field(default=None, description="Pure compact hex string")


class CellResolutionRequest(BaseModel):
    """Request to resolve geographic coordinates for a cellular tower."""
    mcc: int = Field(..., ge=1, le=999)
    mnc: int = Field(..., ge=0, le=999)
    lac: int = Field(..., ge=0, le=65535)
    cid: int = Field(..., ge=0, le=268435455)
    signal_strength: Optional[float] = Field(default=None, ge=-140.0, le=-20.0)
    radio_type: Optional[str] = Field(default="LTE")


class CellResolutionResponse(BaseModel):
    """Result of cell-tower triangulation and geolocation resolution."""
    mcc: int
    mnc: int
    lac: int
    cid: int
    latitude: float
    longitude: float
    accuracy_radius: float = Field(..., description="Coverage accuracy radius in meters")
    carrier: Optional[str] = None
    source: str = Field(..., description="OPENCELLID, MLS, TELECOM_CACHE, or RF_PATH_LOSS_SYNTHESIZER")
    cached: bool = False


class TelemetryRecord(BaseModel):
    """Database representation of an ingested telemetry event."""
    id: int
    device_imei_hash: str
    timestamp: str
    transport: TransportType
    mcc: int
    mnc: int
    lac: int
    cid: int
    signal_strength: float
    carrier_name: Optional[str] = None
    radio_type: str = "LTE"
    timing_advance: Optional[int] = None
    sim_status: str = "ACTIVE"
    sim_imsi_hash: Optional[str] = None
    latitude: float
    longitude: float
    accuracy_radius: float
    resolver_source: str
    raw_payload: Optional[str] = None


class IncidentEvent(BaseModel):
    """Audit incident timeline entry."""
    id: int
    device_imei_hash: str
    timestamp: str
    event_type: str
    severity: str
    details: str


class DeviceResponse(BaseModel):
    """Public device record with current telemetry and recovery status."""
    imei_hash: str
    device_model: str
    owner_name: str
    owner_phone: str
    owner_email: str
    state: DeviceState
    last_seen_at: Optional[str] = None
    last_latitude: Optional[float] = None
    last_longitude: Optional[float] = None
    last_accuracy: Optional[float] = None
    last_mcc: Optional[int] = None
    last_mnc: Optional[int] = None
    last_lac: Optional[int] = None
    last_cid: Optional[int] = None
    last_rssi: Optional[float] = None
    last_transport: Optional[str] = None
    sim_imsi_hash: Optional[str] = None
    registered_at: str
    updated_at: str
    telemetry_count: int = 0
