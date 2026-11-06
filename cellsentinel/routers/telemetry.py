"""
Telemetry Ingestion API Router.
Supports dual-mode receiver:
1. HTTPS REST Endpoint (active mobile data)
2. SMS Gateway Webhook Parser (silent SMS / out-of-band compact hex payloads)
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Request, status

from cellsentinel.models import (
    CellTowerTelemetry,
    SMSWebhookPayload,
    TelemetryRecord,
    TransportType
)
from cellsentinel.services import telemetry_service
from cellsentinel.services.sms_parser import parse_sms_webhook_payload, SMSParseException

router = APIRouter(prefix="/api/v1/telemetry", tags=["Telemetry"])


@router.post(
    "/push",
    response_model=TelemetryRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest cell-tower telemetry via HTTPS REST"
)
async def push_telemetry_endpoint(telemetry: CellTowerTelemetry):
    """
    Standard HTTPS telemetry ingestion endpoint for devices with active mobile data.
    Resolves tower to GPS coordinates & computes dynamic accuracy radius.
    """
    try:
        return await telemetry_service.ingest_telemetry(
            telemetry=telemetry,
            transport=TransportType.HTTPS
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to ingest telemetry: {str(e)}")


@router.post(
    "/sms-webhook",
    response_model=TelemetryRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest out-of-band telemetry from SMS gateway"
)
async def sms_webhook_endpoint(request: Request):
    """
    Out-of-band SMS Gateway Webhook Parser.
    Accepts:
    - Twilio webhook parameters ('From', 'Body')
    - Compact hex binary payloads (e.g. 0xCE + packed header)
    - Bracket notation: '[IMEI_HASH:MCC:MNC:LAC:CID]' or '[IMEI_HASH:MCC:MNC:LAC:CID:RSSI]'
    - Form urlencoded or application/json payloads
    """
    body_payload = {}
    content_type = request.headers.get("content-type", "")

    if "application/json" in content_type:
        try:
            body_payload = await request.json()
        except Exception:
            body_payload = {}
    else:
        try:
            form = await request.form()
            body_payload = dict(form)
        except Exception:
            raw_bytes = await request.body()
            body_payload = {"payload": raw_bytes.decode("utf-8", errors="ignore")}

    try:
        webhook_obj = SMSWebhookPayload(**body_payload)
        telemetry = parse_sms_webhook_payload(webhook_obj)
        return await telemetry_service.ingest_telemetry(
            telemetry=telemetry,
            transport=TransportType.SMS_OUT_OF_BAND
        )
    except SMSParseException as spe:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"SMS Webhook Decoding Error: {str(spe)}"
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Telemetry Ingestion Error: {str(e)}")


@router.get(
    "/recent",
    response_model=List[TelemetryRecord],
    summary="Get recent global telemetry feed"
)
def get_recent_telemetry_endpoint(limit: int = 50):
    """Retrieve recent cellular telemetry logs across all registered devices."""
    return telemetry_service.get_latest_telemetry_logs(limit=limit)
