"""
Telemetry Ingestion API Router.
Accepts authenticated cellular telemetry packets, resolves tower coordinates,
persists records, and publishes live dashboard updates.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from cellsentinel.database import get_db
from cellsentinel.schemas import (
    TelemetryIngestRequest,
    TelemetryIngestResponse,
    TelemetryHistoryItem
)
from cellsentinel.services import telemetry_service, device_service

router = APIRouter(prefix="/api/telemetry", tags=["Telemetry"])


def extract_api_key(
    x_device_token: Optional[str] = Header(None, alias="X-Device-Token"),
    authorization: Optional[str] = Header(None, alias="Authorization")
) -> str:
    """Extract device authentication token from headers."""
    if x_device_token and x_device_token.strip():
        return x_device_token.strip()

    if authorization and authorization.strip():
        parts = authorization.strip().split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1]
        return authorization.strip()

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unauthorized: Missing device authentication token. Provide header 'X-Device-Token' or 'Authorization: Bearer <token>'."
    )


@router.post(
    "",
    response_model=TelemetryIngestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest authenticated cell tower telemetry"
)
async def ingest_telemetry_endpoint(
    payload: TelemetryIngestRequest,
    api_key: str = Depends(extract_api_key),
    db: Session = Depends(get_db)
):
    """
    POST /api/telemetry
    Ingest live cellular tower broadcast parameters from client devices:
    - Authenticates the registered device
    - Validates incoming parameters
    - Resolves tower coordinates using the resolution engine
    - Persists telemetry record and updates device last-seen timestamp
    - Dispatches real-time update to dashboard
    """
    return await telemetry_service.process_telemetry(
        db=db,
        payload=payload,
        api_key=api_key
    )


@router.get(
    "/{identifier}/history",
    response_model=List[TelemetryHistoryItem],
    summary="Get device telemetry transition history"
)
def get_device_history_endpoint(
    identifier: str,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """Retrieve chronological cell tower observations and transition trail."""
    dev = device_service.get_device_by_identifier(db, identifier)
    if not dev:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device identifier '{identifier}' not found."
        )

    return telemetry_service.get_telemetry_history(db, dev.id, limit=limit)
