"""
Dashboard API Router.
Provides operational metrics, search facilities, and real-time Server-Sent Events (SSE).
"""

import asyncio
import hashlib
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from cellsentinel.database import get_db
from cellsentinel.models import Device, Telemetry, CellTowerCache
from cellsentinel.schemas import DeviceDetailResponse, TowerLocation
from cellsentinel.services import device_service, telemetry_service
from cellsentinel.services.tower_resolver import get_carrier_name

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/stats", summary="Get platform operational statistics")
def get_stats(db: Session = Depends(get_db)):
    """Retrieve aggregate counts for dashboard KPI cards."""
    total_devices = db.query(func.count(Device.id)).scalar() or 0
    active_devices = db.query(func.count(Device.id)).filter(Device.device_status == "ACTIVE").scalar() or 0
    total_telemetry = db.query(func.count(Telemetry.id)).scalar() or 0
    cached_towers = db.query(func.count(CellTowerCache.id)).scalar() or 0

    return {
        "total_devices": total_devices,
        "active_devices": active_devices,
        "total_telemetry_events": total_telemetry,
        "cached_cell_towers": cached_towers
    }


@router.get(
    "/search",
    response_model=List[DeviceDetailResponse],
    summary="Search devices by IMEI hash or device ID"
)
def search_devices(
    q: str = Query(..., min_length=1, description="IMEI hash, device ID, or device name query"),
    db: Session = Depends(get_db)
):
    """Search registered devices matching query string."""
    clean = q.strip().lower()
    query = db.query(Device)

    if clean.isdigit():
        conditions = [Device.imei_hash.contains(clean)]
        if len(clean) < 10:
            conditions.append(Device.id == int(clean))
        if len(clean) >= 14:
            raw_hash = hashlib.sha256(clean.encode("utf-8")).hexdigest()
            conditions.append(Device.imei_hash == raw_hash)
        query = query.filter(or_(*conditions))
    else:
        query = query.filter(
            (Device.imei_hash.contains(clean)) |
            (Device.device_name.ilike(f"%{clean}%"))
        )

    devices = query.limit(20).all()
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


@router.get("/events", summary="Real-time Server-Sent Events (SSE) telemetry stream")
async def sse_events():
    """Streaming channel delivering live telemetry updates directly to connected dashboard clients."""
    queue: asyncio.Queue = asyncio.Queue()
    telemetry_service.register_sse_queue(queue)

    async def event_generator():
        try:
            yield "event: ping\ndata: {\"status\": \"connected\"}\n\n"
            while True:
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=25.0)
                    yield f"event: message\ndata: {payload}\n\n"
                except asyncio.TimeoutError:
                    yield "event: keepalive\ndata: {}\n\n"
        finally:
            telemetry_service.unregister_sse_queue(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

