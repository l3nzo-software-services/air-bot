"""
Telemetry Ingestion & Processing Pipeline Service.
Coordinates device authentication, validation, tower resolution, database persistence,
and real-time event broadcasting to the web dashboard.
"""

import asyncio
from datetime import datetime, timezone
import json
import logging
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session

from cellsentinel.models import Device, Telemetry
from cellsentinel.schemas import (
    TelemetryIngestRequest,
    TelemetryIngestResponse,
    TowerLocation,
    TelemetryHistoryItem
)
from cellsentinel.services.device_service import authenticate_device
from cellsentinel.services.tower_resolver import resolve_cell_tower, get_carrier_name

logger = logging.getLogger("cellsentinel.telemetry")

# In-memory subscriber queues for Server-Sent Events (SSE)
_sse_subscribers: List[asyncio.Queue] = []


def register_sse_queue(q: asyncio.Queue) -> None:
    """Register an SSE listener queue."""
    _sse_subscribers.append(q)


def unregister_sse_queue(q: asyncio.Queue) -> None:
    """Remove an SSE listener queue."""
    if q in _sse_subscribers:
        _sse_subscribers.remove(q)


async def broadcast_event(event_type: str, data: Dict[str, Any]) -> None:
    """Broadcast real-time event to all connected dashboard SSE streams."""
    message = json.dumps({"event": event_type, "data": data})
    for q in list(_sse_subscribers):
        try:
            await q.put(message)
        except Exception:
            pass


async def process_telemetry(
    db: Session,
    payload: TelemetryIngestRequest,
    api_key: str
) -> TelemetryIngestResponse:
    """
    Ingest and process cellular tower telemetry from an authenticated device:
    1. Authenticate registered device credentials
    2. Resolve cell tower coordinates via resolver engine
    3. Persist telemetry record into SQLite
    4. Update device's last_seen_timestamp
    5. Broadcast live update to real-time dashboard
    6. Return structured response
    """
    # 1. Authenticate device
    device = authenticate_device(db, payload.device_id, api_key)

    # 2. Resolve cell tower location
    tower_loc = await resolve_cell_tower(
        db=db,
        mcc=payload.mcc,
        mnc=payload.mnc,
        lac=payload.lac,
        cell_id=payload.cell_id
    )

    now_utc = datetime.now(timezone.utc)

    # 3. Save telemetry in database
    telemetry = Telemetry(
        device_id=device.id,
        mcc=payload.mcc,
        mnc=payload.mnc,
        lac=payload.lac,
        cell_id=payload.cell_id,
        signal_strength=payload.signal_strength,
        latitude=tower_loc.latitude,
        longitude=tower_loc.longitude,
        accuracy_radius=tower_loc.accuracy_radius,
        location_source=tower_loc.location_source,
        timestamp=now_utc
    )

    db.add(telemetry)

    # 4. Update device last seen timestamp
    device.last_seen_timestamp = now_utc
    db.commit()
    db.refresh(telemetry)

    # Prepare response payload
    resp = TelemetryIngestResponse(
        success=True,
        device_id=device.imei_hash,
        tower=tower_loc,
        timestamp=now_utc,
        message="Telemetry ingested and processed successfully."
    )

    # 5. Broadcast to dashboard SSE listeners
    asyncio.create_task(
        broadcast_event("TELEMETRY_INGESTED", {
            "device_id": device.id,
            "imei_hash": device.imei_hash,
            "device_name": device.device_name,
            "mcc": payload.mcc,
            "mnc": payload.mnc,
            "lac": payload.lac,
            "cell_id": payload.cell_id,
            "carrier_name": tower_loc.carrier_name,
            "signal_strength": payload.signal_strength,
            "latitude": tower_loc.latitude,
            "longitude": tower_loc.longitude,
            "accuracy_radius": tower_loc.accuracy_radius,
            "location_source": tower_loc.location_source,
            "timestamp": now_utc.isoformat()
        })
    )

    return resp


def get_telemetry_history(
    db: Session,
    device_id: int,
    limit: int = 50
) -> List[TelemetryHistoryItem]:
    """Retrieve chronological telemetry history for a device."""
    records = (
        db.query(Telemetry)
        .filter(Telemetry.device_id == device_id)
        .order_by(Telemetry.timestamp.desc())
        .limit(limit)
        .all()
    )

    results = []
    for r in records:
        carrier = get_carrier_name(r.mcc, r.mnc)
        results.append(
            TelemetryHistoryItem(
                id=r.id,
                mcc=r.mcc,
                mnc=r.mnc,
                lac=r.lac,
                cell_id=r.cell_id,
                carrier_name=carrier,
                signal_strength=r.signal_strength,
                latitude=r.latitude,
                longitude=r.longitude,
                accuracy_radius=r.accuracy_radius,
                location_source=r.location_source,
                timestamp=r.timestamp
            )
        )
    return results
