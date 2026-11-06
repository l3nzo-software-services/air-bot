"""
Dashboard Metrics, SSE Live Event Stream, and Simulation Router.
"""

import asyncio
import json
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from cellsentinel.database import get_db_connection
from cellsentinel.models import (
    DeviceRegisterRequest,
    CellTowerTelemetry,
    TransportType,
    DeviceState
)
from cellsentinel.services import device_service, telemetry_service
from cellsentinel.services.sms_parser import encode_sms_bracket_payload, encode_compact_hex_payload

router = APIRouter(prefix="/api/v1/dashboard", tags=["Dashboard"])


@router.get("/summary", summary="Get dashboard high-level telecom metrics")
def get_dashboard_summary():
    """Retrieve operational metrics for the NOC dashboard."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM devices;")
        total_devices = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM devices WHERE state = 'LOST';")
        lost_devices = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM devices WHERE state = 'RECOVERED';")
        recovered_devices = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM devices WHERE state = 'SECURE';")
        secure_devices = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM telemetry_logs;")
        total_pings = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM cell_cache;")
        cached_towers = cursor.fetchone()[0]

        cursor.execute(
            """
            SELECT COUNT(*) FROM incident_events
            WHERE severity IN ('WARNING', 'CRITICAL');
            """
        )
        active_alerts = cursor.fetchone()[0]

    return {
        "total_devices": total_devices,
        "lost_devices": lost_devices,
        "recovered_devices": recovered_devices,
        "secure_devices": secure_devices,
        "total_telemetry_pings": total_pings,
        "cached_cell_towers": cached_towers,
        "active_alerts": active_alerts
    }


@router.get("/events/stream", summary="Server-Sent Events (SSE) live telemetry feed")
async def events_stream():
    """Real-time SSE channel delivering new telemetry events directly to the Leaflet map."""
    queue: asyncio.Queue = asyncio.Queue()
    telemetry_service.register_sse_subscriber(queue)

    async def event_generator():
        try:
            # Initial connection ping
            yield "event: ping\ndata: {}\n\n"
            while True:
                # Wait for next event or keep-alive heartbeat
                try:
                    event_data = await asyncio.wait_for(queue.get(), timeout=20.0)
                    yield f"event: telemetry\ndata: {json.dumps(event_data)}\n\n"
                except asyncio.TimeoutError:
                    # Send periodic keep-alive
                    yield "event: keepalive\ndata: {}\n\n"
        finally:
            telemetry_service.unregister_sse_subscriber(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/simulate-hop", summary="Simulate a cell tower telemetry ping")
async def simulate_hop(
    imei_hash: str,
    mcc: int = 404,
    mnc: int = 45,
    lac: int = 1234,
    cid: int = 5678,
    rssi: float = -75.0,
    transport: str = "HTTPS"
):
    """
    Test tool to simulate an active cellular ping.
    Supports simulating both standard HTTPS data push and out-of-band Silent SMS Hex PDU.
    """
    device = device_service.get_device_by_hash(imei_hash)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found.")

    if transport.upper() == "SMS":
        # Simulate SMS compact bracket or binary payload
        bracket_payload = encode_sms_bracket_payload(device.imei_hash, mcc, mnc, lac, cid, rssi)
        telemetry = CellTowerTelemetry(
            imei_hash=device.imei_hash,
            mcc=mcc,
            mnc=mnc,
            lac=lac,
            cid=cid,
            signal_strength=rssi,
            raw_payload=bracket_payload
        )
        record = await telemetry_service.ingest_telemetry(telemetry, transport=TransportType.SMS_OUT_OF_BAND)
    else:
        telemetry = CellTowerTelemetry(
            imei_hash=device.imei_hash,
            mcc=mcc,
            mnc=mnc,
            lac=lac,
            cid=cid,
            signal_strength=rssi,
            raw_payload=f"SIMULATED_REST_PUSH:CID={cid}"
        )
        record = await telemetry_service.ingest_telemetry(telemetry, transport=TransportType.HTTPS)

    return {"status": "success", "telemetry": record}


@router.post("/seed-demo", summary="Seed realistic demo device and telecom trajectory")
async def seed_demo():
    """
    Convenience initializer that provisions:
    1. A lost Google Pixel 8 Pro device
    2. A secure Samsung Galaxy S24 Ultra device
    3. Multi-tower telemetry handover sequence in New Delhi (Connaught Place -> Barakhamba -> Mandi House)
    4. Out-of-band silent SMS recovery ping
    """
    # 1. Register lost target device
    dev1_imei = "358941098765432"  # Raw IMEI
    reg1 = DeviceRegisterRequest(
        imei_or_hash=dev1_imei,
        device_model="Google Pixel 8 Pro (Obsidian 256GB)",
        owner_name="Vikramaditya Sharma",
        owner_phone="+91-98110-12345",
        owner_email="v.sharma@telecom-sentinel.org",
        recovery_pin="9876",
        sim_imsi="404450123456789"
    )
    dev1 = device_service.register_device(reg1)
    # Declare device as LOST
    device_service.update_device_state(
        imei_hash=dev1.imei_hash,
        new_state=DeviceState.LOST,
        pin="9876",
        reason="Reported misplaced in Connaught Place Metro Station."
    )

    # 2. Register a second secure device
    dev2_imei = "862145041234567"
    reg2 = DeviceRegisterRequest(
        imei_or_hash=dev2_imei,
        device_model="Samsung Galaxy S24 Ultra",
        owner_name="Ananya Roy",
        owner_phone="+91-98220-54321",
        owner_email="ananya.roy@example.com",
        recovery_pin="1111",
        sim_imsi="404200987654321"
    )
    dev2 = device_service.register_device(reg2)

    # 3. Simulate handover trajectory for LOST device (dev1)
    # Hop 1: Connaught Place Central Hub (MCC 404, MNC 45, LAC 1234, CID 5678, RSSI -68 dBm) via HTTPS
    t1 = CellTowerTelemetry(
        imei_hash=dev1.imei_hash,
        mcc=404,
        mnc=45,
        lac=1234,
        cid=5678,
        signal_strength=-68.0,
        radio_type="LTE",
        timing_advance=2,
        raw_payload="REST_HTTPS_TELEMETRY_PACKET"
    )
    await telemetry_service.ingest_telemetry(t1, transport=TransportType.HTTPS)

    # Hop 2: Barakhamba Road Macrocell (MCC 404, MNC 45, LAC 1234, CID 5679, RSSI -82 dBm) via HTTPS
    t2 = CellTowerTelemetry(
        imei_hash=dev1.imei_hash,
        mcc=404,
        mnc=45,
        lac=1234,
        cid=5679,
        signal_strength=-82.0,
        radio_type="LTE",
        timing_advance=4,
        raw_payload="REST_HTTPS_TELEMETRY_PACKET"
    )
    await telemetry_service.ingest_telemetry(t2, transport=TransportType.HTTPS)

    # Hop 3: Mobile data cut off by unauthorized handler -> Silent SMS Out-of-band PDU triggered!
    # Mandi House Transit Node (MCC 404, MNC 45, LAC 1234, CID 5680, RSSI -91 dBm)
    compact_sms = encode_sms_bracket_payload(dev1.imei_hash, 404, 45, 1234, 5680, -91.0)
    t3 = CellTowerTelemetry(
        imei_hash=dev1.imei_hash,
        mcc=404,
        mnc=45,
        lac=1234,
        cid=5680,
        signal_strength=-91.0,
        radio_type="LTE",
        raw_payload=compact_sms
    )
    await telemetry_service.ingest_telemetry(t3, transport=TransportType.SMS_OUT_OF_BAND)

    return {
        "status": "seeded",
        "lost_device_imei_hash": dev1.imei_hash,
        "secure_device_imei_hash": dev2.imei_hash,
        "message": "Demo devices and realistic tower telemetry trail seeded successfully."
    }
