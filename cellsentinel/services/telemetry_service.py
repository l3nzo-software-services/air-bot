"""
Cellular Telemetry Ingestion & Geolocation Pipeline Service.
Coordinates telemetry receipt (HTTPS & Out-of-Band SMS), tower resolution,
transition detection, SIM swap alerts, trajectory logging, and real-time event dispatch.
"""

import asyncio
from datetime import datetime, timezone
import hashlib
from typing import List, Optional, Dict, Any

from cellsentinel.database import get_db_connection
from cellsentinel.models import (
    CellTowerTelemetry,
    TransportType,
    DeviceState,
    TelemetryRecord,
    DeviceRegisterRequest
)
from cellsentinel.services.device_service import get_device_by_hash, register_device
from cellsentinel.services.resolver import resolve_cell_tower
from cellsentinel.services.rf_math import haversine_distance_meters
from cellsentinel.services.telecom_db import lookup_carrier


# In-memory subscriber list for Server-Sent Events (SSE) live updates
_event_subscribers: List[asyncio.Queue] = []


def register_sse_subscriber(queue: asyncio.Queue) -> None:
    """Register an SSE listener queue."""
    _event_subscribers.append(queue)


def unregister_sse_subscriber(queue: asyncio.Queue) -> None:
    """Remove an SSE listener queue."""
    if queue in _event_subscribers:
        _event_subscribers.remove(queue)


async def broadcast_live_event(event_data: Dict[str, Any]) -> None:
    """Broadcast telemetry event to all active dashboard SSE connections."""
    for q in list(_event_subscribers):
        try:
            await q.put(event_data)
        except Exception:
            pass


async def ingest_telemetry(
    telemetry: CellTowerTelemetry,
    transport: TransportType = TransportType.HTTPS
) -> TelemetryRecord:
    """
    Core telemetry processing pipeline.
    1. Verify or auto-register target device
    2. Triangulate cellular tower & calculate dynamic accuracy radius
    3. Detect tower handovers & distance travelled
    4. Detect SIM IMSI swaps & out-of-band alerts
    5. Persist telemetry and update device state
    6. Broadcast live update to real-time dashboard
    """
    imei_hash = telemetry.imei_hash

    # 1. Resolve Device
    device = get_device_by_hash(imei_hash)
    if not device:
        # Auto-register unknown device upon first cellular ping so telemetry is preserved
        auto_req = DeviceRegisterRequest(
            imei_or_hash=imei_hash,
            device_model="Discovered Cellular Terminal",
            owner_name="Pending Emergency Verification",
            owner_phone="+0000000000",
            owner_email="recovery@cellsentinel.local",
            recovery_pin="1234"
        )
        device = register_device(auto_req)

    # 2. Resolve Cell Tower Geolocation & dynamic accuracy radius
    resolution = await resolve_cell_tower(
        mcc=telemetry.mcc,
        mnc=telemetry.mnc,
        lac=telemetry.lac,
        cid=telemetry.cid,
        signal_strength=telemetry.signal_strength,
        radio_type=telemetry.radio_type or "LTE",
        timing_advance=telemetry.timing_advance
    )

    carrier_name = telemetry.carrier_name or resolution.carrier or lookup_carrier(telemetry.mcc, telemetry.mnc)
    sim_imsi_hash = hashlib.sha256(telemetry.sim_imsi.encode("utf-8")).hexdigest() if telemetry.sim_imsi else device.sim_imsi_hash

    # Check for tower transition
    is_handover = False
    hop_distance_m = 0.0
    if (
        device.last_latitude is not None
        and device.last_longitude is not None
        and (device.last_cid != telemetry.cid or device.last_lac != telemetry.lac)
    ):
        is_handover = True
        hop_distance_m = haversine_distance_meters(
            device.last_latitude,
            device.last_longitude,
            resolution.latitude,
            resolution.longitude
        )

    # Check for SIM status change
    sim_changed = False
    if device.sim_imsi_hash and sim_imsi_hash and device.sim_imsi_hash != sim_imsi_hash:
        sim_changed = True

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Insert telemetry log
        cursor.execute(
            """
            INSERT INTO telemetry_logs (
                device_imei_hash, transport, mcc, mnc, lac, cid, signal_strength,
                carrier_name, radio_type, timing_advance, sim_status, sim_imsi_hash,
                latitude, longitude, accuracy_radius, resolver_source, raw_payload
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                device.imei_hash,
                transport.value,
                telemetry.mcc,
                telemetry.mnc,
                telemetry.lac,
                telemetry.cid,
                telemetry.signal_strength,
                carrier_name,
                telemetry.radio_type or "LTE",
                telemetry.timing_advance,
                telemetry.sim_status or ("CHANGED" if sim_changed else "ACTIVE"),
                sim_imsi_hash,
                resolution.latitude,
                resolution.longitude,
                resolution.accuracy_radius,
                resolution.source,
                telemetry.raw_payload
            )
        )
        record_id = cursor.lastrowid

        # Update Device current hardware telemetry state
        cursor.execute(
            """
            UPDATE devices
            SET last_mcc = ?,
                last_mnc = ?,
                last_lac = ?,
                last_cid = ?,
                last_rssi = ?,
                last_latitude = ?,
                last_longitude = ?,
                last_accuracy = ?,
                last_seen_at = CURRENT_TIMESTAMP,
                last_transport = ?,
                sim_imsi_hash = COALESCE(?, sim_imsi_hash),
                updated_at = CURRENT_TIMESTAMP
            WHERE imei_hash = ?;
            """,
            (
                telemetry.mcc,
                telemetry.mnc,
                telemetry.lac,
                telemetry.cid,
                telemetry.signal_strength,
                resolution.latitude,
                resolution.longitude,
                resolution.accuracy_radius,
                transport.value,
                sim_imsi_hash,
                device.imei_hash
            )
        )

        # Audit events for handover or alerts
        if transport == TransportType.SMS_OUT_OF_BAND:
            cursor.execute(
                """
                INSERT INTO incident_events (device_imei_hash, event_type, severity, details)
                VALUES (?, 'OUT_OF_BAND_SMS_TELEMETRY', 'WARNING', ?);
                """,
                (
                    device.imei_hash,
                    f"Offline telemetry received via silent SMS. Tower: MCC {telemetry.mcc} MNC {telemetry.mnc} LAC {telemetry.lac} CID {telemetry.cid} (RSSI: {telemetry.signal_strength} dBm)."
                )
            )

        if is_handover:
            cursor.execute(
                """
                INSERT INTO incident_events (device_imei_hash, event_type, severity, details)
                VALUES (?, 'CELL_TOWER_HANDOVER', 'INFO', ?);
                """,
                (
                    device.imei_hash,
                    f"Handover detected: previous CID {device.last_cid} -> current CID {telemetry.cid} (Transition distance: {round(hop_distance_m, 1)}m)."
                )
            )

        if sim_changed:
            cursor.execute(
                """
                INSERT INTO incident_events (device_imei_hash, event_type, severity, details)
                VALUES (?, 'SIM_CARD_SWAP_DETECTED', 'CRITICAL', 'SIM IMSI mismatch detected! Possible unauthorized SIM replacement.');
                """,
                (device.imei_hash,)
            )

    record = TelemetryRecord(
        id=record_id,
        device_imei_hash=device.imei_hash,
        timestamp=datetime.now(timezone.utc).isoformat(),
        transport=transport,
        mcc=telemetry.mcc,
        mnc=telemetry.mnc,
        lac=telemetry.lac,
        cid=telemetry.cid,
        signal_strength=telemetry.signal_strength,
        carrier_name=carrier_name,
        radio_type=telemetry.radio_type or "LTE",
        timing_advance=telemetry.timing_advance,
        sim_status=telemetry.sim_status or ("CHANGED" if sim_changed else "ACTIVE"),
        sim_imsi_hash=sim_imsi_hash,
        latitude=resolution.latitude,
        longitude=resolution.longitude,
        accuracy_radius=resolution.accuracy_radius,
        resolver_source=resolution.source,
        raw_payload=telemetry.raw_payload
    )

    # Dispatch to live SSE listeners
    asyncio.create_task(
        broadcast_live_event({
            "type": "TELEMETRY_INGESTED",
            "telemetry": record.model_dump(),
            "device": {
                "imei_hash": device.imei_hash,
                "device_model": device.device_model,
                "state": device.state.value,
                "owner_name": device.owner_name
            }
        })
    )

    return record


def get_device_trajectory(
    imei_hash: str,
    limit: int = 200
) -> List[TelemetryRecord]:
    """Retrieve chronologically ordered telemetry breadcrumb trajectory for map visualization."""
    device = get_device_by_hash(imei_hash)
    if not device:
        return []

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM telemetry_logs
            WHERE device_imei_hash = ?
            ORDER BY timestamp ASC
            LIMIT ?;
            """,
            (device.imei_hash, limit)
        )
        rows = cursor.fetchall()
        return [
            TelemetryRecord(
                id=r["id"],
                device_imei_hash=r["device_imei_hash"],
                timestamp=str(r["timestamp"]),
                transport=TransportType(r["transport"]),
                mcc=r["mcc"],
                mnc=r["mnc"],
                lac=r["lac"],
                cid=r["cid"],
                signal_strength=r["signal_strength"],
                carrier_name=r["carrier_name"],
                radio_type=r["radio_type"],
                timing_advance=r["timing_advance"],
                sim_status=r["sim_status"],
                sim_imsi_hash=r["sim_imsi_hash"],
                latitude=r["latitude"],
                longitude=r["longitude"],
                accuracy_radius=r["accuracy_radius"],
                resolver_source=r["resolver_source"],
                raw_payload=r["raw_payload"]
            )
            for r in rows
        ]


def get_latest_telemetry_logs(limit: int = 50) -> List[TelemetryRecord]:
    """Retrieve global recent telemetry across all devices for dashboard feed."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM telemetry_logs
            ORDER BY timestamp DESC
            LIMIT ?;
            """,
            (limit,)
        )
        rows = cursor.fetchall()
        return [
            TelemetryRecord(
                id=r["id"],
                device_imei_hash=r["device_imei_hash"],
                timestamp=str(r["timestamp"]),
                transport=TransportType(r["transport"]),
                mcc=r["mcc"],
                mnc=r["mnc"],
                lac=r["lac"],
                cid=r["cid"],
                signal_strength=r["signal_strength"],
                carrier_name=r["carrier_name"],
                radio_type=r["radio_type"],
                timing_advance=r["timing_advance"],
                sim_status=r["sim_status"],
                sim_imsi_hash=r["sim_imsi_hash"],
                latitude=r["latitude"],
                longitude=r["longitude"],
                accuracy_radius=r["accuracy_radius"],
                resolver_source=r["resolver_source"],
                raw_payload=r["raw_payload"]
            )
            for r in rows
        ]
