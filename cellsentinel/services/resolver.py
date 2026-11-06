"""
Cell-Tower Triangulation & Geolocation Resolver Engine.
Resolves MCC, MNC, LAC, CID, and Signal Strength into high-precision Latitude,
Longitude, and dynamic Accuracy Radius using multi-tier fallback architecture:
1. SQLite Cell Cache
2. Verified Telecom Cell Directory
3. OpenCellID API
4. Mozilla Location Services (MLS / Ichnaea) API
5. Offline RF Propagation Path-Loss Synthesizer
"""

import httpx
from datetime import datetime
from typing import Optional, Dict, Any

from cellsentinel.config import settings
from cellsentinel.database import get_db_connection
from cellsentinel.models import CellResolutionResponse
from cellsentinel.services.rf_math import compute_accuracy_radius
from cellsentinel.services.telecom_db import (
    VERIFIED_CELL_TOWERS,
    lookup_carrier,
    synthesize_offline_coordinates
)


def _get_cached_cell(mcc: int, mnc: int, lac: int, cid: int) -> Optional[Dict[str, Any]]:
    """Query persistent SQLite cache for known cell tower."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT latitude, longitude, range_meters, carrier, source, query_count
            FROM cell_cache
            WHERE mcc = ? AND mnc = ? AND lac = ? AND cid = ?;
            """,
            (mcc, mnc, lac, cid)
        )
        row = cursor.fetchone()
        if row:
            cursor.execute(
                """
                UPDATE cell_cache
                SET query_count = query_count + 1, updated_at = CURRENT_TIMESTAMP
                WHERE mcc = ? AND mnc = ? AND lac = ? AND cid = ?;
                """,
                (mcc, mnc, lac, cid)
            )
            return dict(row)
    return None


def _save_cell_to_cache(
    mcc: int,
    mnc: int,
    lac: int,
    cid: int,
    latitude: float,
    longitude: float,
    range_meters: float,
    carrier: str,
    source: str
) -> None:
    """Store or update resolved cell tower coordinates in SQLite cache."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO cell_cache (mcc, mnc, lac, cid, latitude, longitude, range_meters, carrier, source, query_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            ON CONFLICT(mcc, mnc, lac, cid) DO UPDATE SET
                latitude = excluded.latitude,
                longitude = excluded.longitude,
                range_meters = excluded.range_meters,
                carrier = excluded.carrier,
                source = excluded.source,
                query_count = cell_cache.query_count + 1,
                updated_at = CURRENT_TIMESTAMP;
            """,
            (mcc, mnc, lac, cid, latitude, longitude, range_meters, carrier, source)
        )


async def _query_opencellid(
    mcc: int, mnc: int, lac: int, cid: int
) -> Optional[Dict[str, Any]]:
    """Query official OpenCellID REST API if API key is provided."""
    if not settings.OPENCELLID_API_KEY:
        return None

    params = {
        "key": settings.OPENCELLID_API_KEY,
        "mcc": mcc,
        "mnc": mnc,
        "lac": lac,
        "cellid": cid,
        "format": "json"
    }

    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.get(settings.OPENCELLID_BASE_URL, params=params)
            if resp.status_code == 200:
                data = resp.json()
                if "lat" in data and "lon" in data:
                    return {
                        "latitude": float(data["lat"]),
                        "longitude": float(data["lon"]),
                        "range_meters": float(data.get("range", 850.0)),
                        "carrier": lookup_carrier(mcc, mnc),
                        "source": "OPENCELLID"
                    }
    except Exception:
        # Fall back gracefully on timeout or network error
        pass
    return None


async def _query_mls(
    mcc: int, mnc: int, lac: int, cid: int, signal_strength: float = -75.0, radio_type: str = "LTE"
) -> Optional[Dict[str, Any]]:
    """Query Mozilla Location Services (MLS / Ichnaea) or Unwired Labs API."""
    key = settings.MLS_API_KEY or settings.UNWIRED_API_KEY
    if not key:
        return None

    base_url = settings.MLS_BASE_URL if settings.MLS_API_KEY else settings.UNWIRED_BASE_URL

    payload = {
        "cellTowers": [
            {
                "radio": radio_type.lower(),
                "mobileCountryCode": mcc,
                "mobileNetworkCode": mnc,
                "locationAreaCode": lac,
                "cellId": cid,
                "signalStrength": int(round(signal_strength))
            }
        ]
    }

    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.post(f"{base_url}?key={key}", json=payload)
            if resp.status_code == 200:
                data = resp.json()
                if "location" in data and "lat" in data["location"]:
                    return {
                        "latitude": float(data["location"]["lat"]),
                        "longitude": float(data["location"]["lng"]),
                        "range_meters": float(data.get("accuracy", 750.0)),
                        "carrier": lookup_carrier(mcc, mnc),
                        "source": "MLS"
                    }
    except Exception:
        pass
    return None


async def resolve_cell_tower(
    mcc: int,
    mnc: int,
    lac: int,
    cid: int,
    signal_strength: float = -75.0,
    radio_type: str = "LTE",
    timing_advance: Optional[int] = None
) -> CellResolutionResponse:
    """
    Primary automated resolver function.
    Computes Latitude, Longitude, and dynamic Accuracy Radius in meters.
    """
    # 1. Check persistent SQLite cache
    cached = _get_cached_cell(mcc, mnc, lac, cid)
    if cached:
        acc_radius = compute_accuracy_radius(
            rssi_dbm=signal_strength,
            timing_advance=timing_advance,
            radio_type=radio_type,
            base_range=cached["range_meters"]
        )
        return CellResolutionResponse(
            mcc=mcc,
            mnc=mnc,
            lac=lac,
            cid=cid,
            latitude=cached["latitude"],
            longitude=cached["longitude"],
            accuracy_radius=acc_radius,
            carrier=cached["carrier"],
            source=cached["source"],
            cached=True
        )

    # 2. Check verified telecom reference dictionary
    cell_key = (mcc, mnc, lac, cid)
    if cell_key in VERIFIED_CELL_TOWERS:
        tower = VERIFIED_CELL_TOWERS[cell_key]
        _save_cell_to_cache(
            mcc=mcc,
            mnc=mnc,
            lac=lac,
            cid=cid,
            latitude=tower["latitude"],
            longitude=tower["longitude"],
            range_meters=tower["base_range"],
            carrier=tower["carrier"],
            source="TELECOM_CACHE"
        )
        acc_radius = compute_accuracy_radius(
            rssi_dbm=signal_strength,
            timing_advance=timing_advance,
            radio_type=radio_type,
            base_range=tower["base_range"]
        )
        return CellResolutionResponse(
            mcc=mcc,
            mnc=mnc,
            lac=lac,
            cid=cid,
            latitude=tower["latitude"],
            longitude=tower["longitude"],
            accuracy_radius=acc_radius,
            carrier=tower["carrier"],
            source="TELECOM_CACHE",
            cached=False
        )

    # 3. Query OpenCellID
    ocid_res = await _query_opencellid(mcc, mnc, lac, cid)
    if ocid_res:
        _save_cell_to_cache(
            mcc=mcc,
            mnc=mnc,
            lac=lac,
            cid=cid,
            latitude=ocid_res["latitude"],
            longitude=ocid_res["longitude"],
            range_meters=ocid_res["range_meters"],
            carrier=ocid_res["carrier"],
            source=ocid_res["source"]
        )
        acc_radius = compute_accuracy_radius(
            rssi_dbm=signal_strength,
            timing_advance=timing_advance,
            radio_type=radio_type,
            base_range=ocid_res["range_meters"]
        )
        return CellResolutionResponse(
            mcc=mcc,
            mnc=mnc,
            lac=lac,
            cid=cid,
            latitude=ocid_res["latitude"],
            longitude=ocid_res["longitude"],
            accuracy_radius=acc_radius,
            carrier=ocid_res["carrier"],
            source="OPENCELLID",
            cached=False
        )

    # 4. Query Mozilla Location Services
    mls_res = await _query_mls(mcc, mnc, lac, cid, signal_strength, radio_type)
    if mls_res:
        _save_cell_to_cache(
            mcc=mcc,
            mnc=mnc,
            lac=lac,
            cid=cid,
            latitude=mls_res["latitude"],
            longitude=mls_res["longitude"],
            range_meters=mls_res["range_meters"],
            carrier=mls_res["carrier"],
            source=mls_res["source"]
        )
        acc_radius = compute_accuracy_radius(
            rssi_dbm=signal_strength,
            timing_advance=timing_advance,
            radio_type=radio_type,
            base_range=mls_res["range_meters"]
        )
        return CellResolutionResponse(
            mcc=mcc,
            mnc=mnc,
            lac=lac,
            cid=cid,
            latitude=mls_res["latitude"],
            longitude=mls_res["longitude"],
            accuracy_radius=acc_radius,
            carrier=mls_res["carrier"],
            source="MLS",
            cached=False
        )

    # 5. Deterministic RF Geographic Synthesizer fallback
    lat, lon, base_range, carrier = synthesize_offline_coordinates(mcc, mnc, lac, cid)
    _save_cell_to_cache(
        mcc=mcc,
        mnc=mnc,
        lac=lac,
        cid=cid,
        latitude=lat,
        longitude=lon,
        range_meters=base_range,
        carrier=carrier,
        source="RF_PATH_LOSS_SYNTHESIZER"
    )
    acc_radius = compute_accuracy_radius(
        rssi_dbm=signal_strength,
        timing_advance=timing_advance,
        radio_type=radio_type,
        base_range=base_range
    )
    return CellResolutionResponse(
        mcc=mcc,
        mnc=mnc,
        lac=lac,
        cid=cid,
        latitude=lat,
        longitude=lon,
        accuracy_radius=acc_radius,
        carrier=carrier,
        source="RF_PATH_LOSS_SYNTHESIZER",
        cached=False
    )

