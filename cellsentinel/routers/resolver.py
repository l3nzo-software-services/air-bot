"""
Standalone Cell-Tower Triangulation & Geolocation Resolver Router.
"""

from fastapi import APIRouter, HTTPException, Query
from cellsentinel.models import CellResolutionRequest, CellResolutionResponse
from cellsentinel.services.resolver import resolve_cell_tower

router = APIRouter(prefix="/api/v1/resolver", tags=["Resolver"])


@router.post(
    "/lookup",
    response_model=CellResolutionResponse,
    summary="Resolve cell-tower parameters to coordinates"
)
async def resolve_lookup_endpoint(req: CellResolutionRequest):
    """
    Direct resolver endpoint to test cellular parameters (MCC, MNC, LAC, CID, Signal Strength)
    and compute Latitude, Longitude, and Accuracy Radius.
    """
    try:
        return await resolve_cell_tower(
            mcc=req.mcc,
            mnc=req.mnc,
            lac=req.lac,
            cid=req.cid,
            signal_strength=req.signal_strength if req.signal_strength is not None else -75.0,
            radio_type=req.radio_type or "LTE"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Resolver error: {str(e)}")


@router.get(
    "/quick",
    response_model=CellResolutionResponse,
    summary="Quick GET resolver for browser testing"
)
async def quick_lookup_endpoint(
    mcc: int = Query(404, description="Mobile Country Code"),
    mnc: int = Query(45, description="Mobile Network Code"),
    lac: int = Query(1234, description="Location Area Code"),
    cid: int = Query(5678, description="Cell Tower ID"),
    rssi: float = Query(-75.0, description="Signal strength in dBm")
):
    """Convenience GET endpoint for rapid testing and sanity verification."""
    return await resolve_cell_tower(
        mcc=mcc,
        mnc=mnc,
        lac=lac,
        cid=cid,
        signal_strength=rssi,
        radio_type="LTE"
    )

