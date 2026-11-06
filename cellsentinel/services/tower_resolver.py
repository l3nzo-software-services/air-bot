"""
Cell Tower Resolution Engine.
Resolves MCC, MNC, LAC, and Cell_ID into verified coordinates and coverage radius.
Strictly complies with engineering directives:
- Never fabricates coordinates
- Never uses country centroids as tower locations
- Never invents accuracy radius
- Returns explicit UNRESOLVED when no reliable data exists
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import httpx
from sqlalchemy.orm import Session

from cellsentinel.config import settings
from cellsentinel.models import CellTowerCache
from cellsentinel.schemas import TowerLocation

logger = logging.getLogger("cellsentinel.tower_resolver")

# Global recognized carrier directory for friendly labeling
CARRIER_REGISTRY: Dict[tuple, str] = {
    # India
    (404, 45): "Bharti Airtel (Airtel India)",
    (404, 20): "Reliance Jio Infocomm",
    (404, 11): "Vodafone Idea (Vi)",
    (404, 71): "BSNL Mobile",
    (404, 86): "Vodafone Idea (Vi)",
    (405, 854): "Reliance Jio 5G",
    (405, 861): "Bharti Airtel 5G NSA",
    # USA
    (310, 410): "AT&T Mobility (USA)",
    (310, 260): "T-Mobile USA",
    (310, 480): "Verizon Wireless (USA)",
    (311, 480): "Verizon Ultra Wideband",
    # UK
    (234, 30): "EE (UK)",
    (234, 15): "Vodafone UK",
    (234, 10): "O2 (UK)",
    (234, 20): "Three (UK)",
    # France
    (208, 1): "Orange (France)",
    (208, 10): "SFR (France)",
    (208, 15): "Free Mobile (France)",
    # Germany
    (262, 1): "Telekom Deutschland",
    (262, 2): "Vodafone Germany",
    (262, 3): "O2 Telefónica Germany",
}


def get_carrier_name(mcc: int, mnc: int) -> str:
    """Return recognized carrier name or formatted MCC/MNC string."""
    return CARRIER_REGISTRY.get(
        (mcc, mnc),
        f"Cellular Network (MCC {mcc} / MNC {mnc})"
    )


async def _query_opencellid_api(
    mcc: int, mnc: int, lac: int, cell_id: int
) -> Optional[Dict[str, Any]]:
    """
    Query official OpenCellID API with timeout, retry limit, and robust error handling.
    """
    if not settings.OPENCELLID_API_KEY:
        return None

    params = {
        "key": settings.OPENCELLID_API_KEY,
        "mcc": mcc,
        "mnc": mnc,
        "lac": lac,
        "cellid": cell_id,
        "format": "json"
    }

    retries = settings.API_MAX_RETRIES
    for attempt in range(retries):
        try:
            async with httpx.AsyncClient(timeout=settings.API_TIMEOUT_SECONDS) as client:
                res = await client.get(settings.OPENCELLID_BASE_URL, params=params)
                if res.status_code == 200:
                    data = res.json()
                    if "lat" in data and "lon" in data:
                        # Only return accuracy if reported by the API; do not invent
                        acc = float(data["range"]) if "range" in data and data["range"] is not None else None
                        return {
                            "latitude": float(data["lat"]),
                            "longitude": float(data["lon"]),
                            "accuracy_radius": acc,
                            "source": "OPENCELLID"
                        }
                elif res.status_code in (404, 400):
                    # Definite not found or bad request from OpenCellID
                    break
        except Exception as e:
            logger.warning(f"OpenCellID API query attempt {attempt + 1} failed: {e}")
            if attempt == retries - 1:
                break

    return None


def _check_local_reference_file(mcc: int, mnc: int, lac: int, cell_id: int) -> Optional[Dict[str, Any]]:
    """Check verified offline reference data from data/verified_towers.json."""
    if not settings.VERIFIED_TOWERS_FILE.exists():
        return None

    try:
        with open(settings.VERIFIED_TOWERS_FILE, "r", encoding="utf-8") as f:
            towers = json.load(f)
            for t in towers:
                if (
                    t["mcc"] == mcc
                    and t["mnc"] == mnc
                    and t["lac"] == lac
                    and t["cell_id"] == cell_id
                ):
                    return {
                        "latitude": t["latitude"],
                        "longitude": t["longitude"],
                        "accuracy_radius": t.get("accuracy_radius"),
                        "source": "LOCAL_VERIFIED"
                    }
    except Exception as e:
        logger.error(f"Error reading verified towers file: {e}")

    return None


async def resolve_cell_tower(
    db: Session,
    mcc: int,
    mnc: int,
    lac: int,
    cell_id: int
) -> TowerLocation:
    """
    Main resolution engine function.
    
    Resolution Priority:
    1. Check local SQLite tower cache.
    2. Query OpenCellID API when a valid API key is configured.
    3. Use verified local reference data as fallback.
    4. Return an explicit unresolved result if no reliable location is available.
    """
    carrier_name = get_carrier_name(mcc, mnc)
    now_utc = datetime.now(timezone.utc)

    # 1. Check local SQLite tower cache
    cached = (
        db.query(CellTowerCache)
        .filter(
            CellTowerCache.mcc == mcc,
            CellTowerCache.mnc == mnc,
            CellTowerCache.lac == lac,
            CellTowerCache.cell_id == cell_id
        )
        .first()
    )

    if cached:
        return TowerLocation(
            mcc=mcc,
            mnc=mnc,
            lac=lac,
            cell_id=cell_id,
            carrier_name=carrier_name,
            latitude=cached.latitude,
            longitude=cached.longitude,
            accuracy_radius=cached.accuracy_radius,
            location_source="CACHE"
        )

    # 2. Query OpenCellID API
    ocid_result = await _query_opencellid_api(mcc, mnc, lac, cell_id)
    if ocid_result:
        # Cache resolved result
        new_cache = CellTowerCache(
            mcc=mcc,
            mnc=mnc,
            lac=lac,
            cell_id=cell_id,
            latitude=ocid_result["latitude"],
            longitude=ocid_result["longitude"],
            accuracy_radius=ocid_result["accuracy_radius"],
            source=ocid_result["source"],
            last_updated=now_utc
        )
        db.add(new_cache)
        db.commit()

        return TowerLocation(
            mcc=mcc,
            mnc=mnc,
            lac=lac,
            cell_id=cell_id,
            carrier_name=carrier_name,
            latitude=ocid_result["latitude"],
            longitude=ocid_result["longitude"],
            accuracy_radius=ocid_result["accuracy_radius"],
            location_source=ocid_result["source"]
        )

    # 3. Check verified local reference data
    local_result = _check_local_reference_file(mcc, mnc, lac, cell_id)
    if local_result:
        # Cache it for future queries
        new_cache = CellTowerCache(
            mcc=mcc,
            mnc=mnc,
            lac=lac,
            cell_id=cell_id,
            latitude=local_result["latitude"],
            longitude=local_result["longitude"],
            accuracy_radius=local_result["accuracy_radius"],
            source=local_result["source"],
            last_updated=now_utc
        )
        db.add(new_cache)
        db.commit()

        return TowerLocation(
            mcc=mcc,
            mnc=mnc,
            lac=lac,
            cell_id=cell_id,
            carrier_name=carrier_name,
            latitude=local_result["latitude"],
            longitude=local_result["longitude"],
            accuracy_radius=local_result["accuracy_radius"],
            location_source=local_result["source"]
        )

    # 4. Explicit UNRESOLVED result
    # Do not invent coordinates or centroid approximations
    return TowerLocation(
        mcc=mcc,
        mnc=mnc,
        lac=lac,
        cell_id=cell_id,
        carrier_name=carrier_name,
        latitude=None,
        longitude=None,
        accuracy_radius=None,
        location_source="UNRESOLVED"
    )
