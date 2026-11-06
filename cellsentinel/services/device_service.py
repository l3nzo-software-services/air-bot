"""
Device Identity & Hardware Registry Service.
Handles registration of device hardware identifiers (IMEI SHA-256 hash, Model,
Owner Emergency Contacts), and lifecycle state management [SECURE, LOST, RECOVERED].
"""

import hashlib
import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any

from cellsentinel.database import get_db_connection
from cellsentinel.models import (
    DeviceRegisterRequest,
    DeviceState,
    DeviceResponse,
    IncidentEvent
)


def _hash_pin(pin: str) -> str:
    """Hash recovery PIN with salt."""
    salt = "CellSentinel-Salt-v1"
    return hashlib.sha256(f"{salt}:{pin}".encode("utf-8")).hexdigest()


def register_device(req: DeviceRegisterRequest) -> DeviceResponse:
    """Register or update device hardware identity in registry."""
    imei_hash = req.imei_or_hash
    pin_hash = _hash_pin(req.recovery_pin) if req.recovery_pin else None
    sim_imsi_hash = hashlib.sha256(req.sim_imsi.encode("utf-8")).hexdigest() if req.sim_imsi else None

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Check if already registered
        cursor.execute("SELECT imei_hash, state FROM devices WHERE imei_hash = ?;", (imei_hash,))
        existing = cursor.fetchone()

        if existing:
            cursor.execute(
                """
                UPDATE devices
                SET device_model = ?,
                    owner_name = ?,
                    owner_phone = ?,
                    owner_email = ?,
                    recovery_pin_hash = COALESCE(?, recovery_pin_hash),
                    sim_imsi_hash = COALESCE(?, sim_imsi_hash),
                    updated_at = CURRENT_TIMESTAMP
                WHERE imei_hash = ?;
                """,
                (req.device_model, req.owner_name, req.owner_phone, req.owner_email, pin_hash, sim_imsi_hash, imei_hash)
            )
            event_type = "DEVICE_UPDATED"
            details = f"Device metadata updated for model {req.device_model} (Owner: {req.owner_name})"
        else:
            cursor.execute(
                """
                INSERT INTO devices (
                    imei_hash, device_model, owner_name, owner_phone, owner_email,
                    recovery_pin_hash, state, sim_imsi_hash
                ) VALUES (?, ?, ?, ?, ?, ?, 'SECURE', ?);
                """,
                (imei_hash, req.device_model, req.owner_name, req.owner_phone, req.owner_email, pin_hash, sim_imsi_hash)
            )
            event_type = "DEVICE_REGISTERED"
            details = f"New hardware identity registered for {req.device_model}. Status: SECURE."

        # Audit event
        cursor.execute(
            """
            INSERT INTO incident_events (device_imei_hash, event_type, severity, details)
            VALUES (?, ?, 'INFO', ?);
            """,
            (imei_hash, event_type, details)
        )

    return get_device_by_hash(imei_hash)


def get_device_by_hash(imei_hash: str) -> Optional[DeviceResponse]:
    """Retrieve device record by full 64-char hash or prefix."""
    clean = imei_hash.strip().lower()

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Direct exact match
        cursor.execute(
            """
            SELECT d.*, COUNT(t.id) as telemetry_count
            FROM devices d
            LEFT JOIN telemetry_logs t ON d.imei_hash = t.device_imei_hash
            WHERE d.imei_hash = ?
            GROUP BY d.imei_hash;
            """,
            (clean,)
        )
        row = cursor.fetchone()

        # If not found and search term is prefix (e.g. 16-32 chars)
        if not row and len(clean) >= 8:
            cursor.execute(
                """
                SELECT d.*, COUNT(t.id) as telemetry_count
                FROM devices d
                LEFT JOIN telemetry_logs t ON d.imei_hash = t.device_imei_hash
                WHERE d.imei_hash LIKE ?
                GROUP BY d.imei_hash
                LIMIT 1;
                """,
                (f"{clean}%",)
            )
            row = cursor.fetchone()

        if not row:
            return None

        return DeviceResponse(
            imei_hash=row["imei_hash"],
            device_model=row["device_model"],
            owner_name=row["owner_name"],
            owner_phone=row["owner_phone"],
            owner_email=row["owner_email"],
            state=DeviceState(row["state"]),
            last_seen_at=row["last_seen_at"],
            last_latitude=row["last_latitude"],
            last_longitude=row["last_longitude"],
            last_accuracy=row["last_accuracy"],
            last_mcc=row["last_mcc"],
            last_mnc=row["last_mnc"],
            last_lac=row["last_lac"],
            last_cid=row["last_cid"],
            last_rssi=row["last_rssi"],
            last_transport=row["last_transport"],
            sim_imsi_hash=row["sim_imsi_hash"],
            registered_at=str(row["registered_at"]),
            updated_at=str(row["updated_at"]),
            telemetry_count=row["telemetry_count"]
        )


def list_devices(
    state_filter: Optional[DeviceState] = None,
    query: Optional[str] = None
) -> List[DeviceResponse]:
    """List registered devices with optional state filtering and search."""
    sql = """
        SELECT d.*, COUNT(t.id) as telemetry_count
        FROM devices d
        LEFT JOIN telemetry_logs t ON d.imei_hash = t.device_imei_hash
        WHERE 1=1
    """
    params: List[Any] = []

    if state_filter:
        sql += " AND d.state = ?"
        params.append(state_filter.value)

    if query:
        q = f"%{query.strip()}%"
        sql += " AND (d.imei_hash LIKE ? OR d.device_model LIKE ? OR d.owner_name LIKE ? OR d.owner_phone LIKE ?)"
        params.extend([q, q, q, q])

    sql += " GROUP BY d.imei_hash ORDER BY d.updated_at DESC;"

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        rows = cursor.fetchall()

        results = []
        for row in rows:
            results.append(
                DeviceResponse(
                    imei_hash=row["imei_hash"],
                    device_model=row["device_model"],
                    owner_name=row["owner_name"],
                    owner_phone=row["owner_phone"],
                    owner_email=row["owner_email"],
                    state=DeviceState(row["state"]),
                    last_seen_at=row["last_seen_at"],
                    last_latitude=row["last_latitude"],
                    last_longitude=row["last_longitude"],
                    last_accuracy=row["last_accuracy"],
                    last_mcc=row["last_mcc"],
                    last_mnc=row["last_mnc"],
                    last_lac=row["last_lac"],
                    last_cid=row["last_cid"],
                    last_rssi=row["last_rssi"],
                    last_transport=row["last_transport"],
                    sim_imsi_hash=row["sim_imsi_hash"],
                    registered_at=str(row["registered_at"]),
                    updated_at=str(row["updated_at"]),
                    telemetry_count=row["telemetry_count"]
                )
            )
        return results


def update_device_state(
    imei_hash: str,
    new_state: DeviceState,
    pin: Optional[str] = None,
    reason: Optional[str] = None
) -> DeviceResponse:
    """Transition device state: [SECURE, LOST, RECOVERED] with audit logging."""
    device = get_device_by_hash(imei_hash)
    if not device:
        raise ValueError(f"Device with IMEI hash {imei_hash} not found.")

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # If PIN is configured, verify PIN
        cursor.execute("SELECT recovery_pin_hash FROM devices WHERE imei_hash = ?;", (device.imei_hash,))
        stored_row = cursor.fetchone()
        stored_pin_hash = stored_row["recovery_pin_hash"] if stored_row else None

        if stored_pin_hash and pin:
            computed_pin_hash = _hash_pin(pin)
            if computed_pin_hash != stored_pin_hash:
                cursor.execute(
                    """
                    INSERT INTO incident_events (device_imei_hash, event_type, severity, details)
                    VALUES (?, 'UNAUTHORIZED_STATE_CHANGE_ATTEMPT', 'WARNING', 'Failed PIN attempt for status change.');
                    """,
                    (device.imei_hash,)
                )
                raise PermissionError("Invalid recovery PIN provided.")

        cursor.execute(
            """
            UPDATE devices
            SET state = ?, updated_at = CURRENT_TIMESTAMP
            WHERE imei_hash = ?;
            """,
            (new_state.value, device.imei_hash)
        )

        # Audit event based on new state
        severity = "INFO"
        if new_state == DeviceState.LOST:
            severity = "CRITICAL"
            event_type = "DEVICE_DECLARED_LOST"
            desc = f"Emergency broadcast activated. Device state changed to LOST. Reason: {reason or 'Owner reported missing.'}"
        elif new_state == DeviceState.RECOVERED:
            severity = "INFO"
            event_type = "DEVICE_RECOVERED"
            desc = f"Device successfully marked RECOVERED. Reason: {reason or 'Device restored to owner.'}"
        else:
            event_type = "DEVICE_SET_SECURE"
            desc = f"Device reset to SECURE normal operating state. Reason: {reason or 'Administrative update.'}"

        cursor.execute(
            """
            INSERT INTO incident_events (device_imei_hash, event_type, severity, details)
            VALUES (?, ?, ?, ?);
            """,
            (device.imei_hash, event_type, severity, desc)
        )

    return get_device_by_hash(device.imei_hash)


def get_device_timeline_events(imei_hash: str) -> List[IncidentEvent]:
    """Retrieve audit events for device incident timeline."""
    device = get_device_by_hash(imei_hash)
    if not device:
        return []

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, device_imei_hash, timestamp, event_type, severity, details
            FROM incident_events
            WHERE device_imei_hash = ?
            ORDER BY timestamp DESC
            LIMIT 100;
            """,
            (device.imei_hash,)
        )
        rows = cursor.fetchall()
        return [
            IncidentEvent(
                id=r["id"],
                device_imei_hash=r["device_imei_hash"],
                timestamp=str(r["timestamp"]),
                event_type=r["event_type"],
                severity=r["severity"],
                details=r["details"]
            )
            for r in rows
        ]
