"""
RF Propagation & Geolocation Mathematical Engine for Cellular Telemetry.
Implements Log-Distance Path Loss, Hata-Okumura models, Timing Advance adjustments,
and Geodetic distance calculations.
"""

import math
from typing import Tuple, Optional
from cellsentinel.config import settings


def compute_path_loss_distance(
    rssi_dbm: float,
    reference_power_dbm: Optional[float] = None,
    path_loss_exponent: Optional[float] = None
) -> float:
    """
    Calculate estimated distance in meters from cell tower antenna to user equipment (UE)
    using the Log-Distance Path Loss model:
        PL(d) = P0 - RSSI
        d = 10 ** ((P0 - RSSI) / (10 * n))
    """
    p0 = reference_power_dbm if reference_power_dbm is not None else settings.REFERENCE_POWER_DBM
    n = path_loss_exponent if path_loss_exponent is not None else settings.PATH_LOSS_EXPONENT

    # Path loss in dB
    path_loss = p0 - rssi_dbm
    if path_loss <= 0:
        return 1.0  # Immediate proximity (< 1 meter)

    # Solve for distance
    estimated_distance = 10.0 ** (path_loss / (10.0 * n))
    return estimated_distance


def compute_accuracy_radius(
    rssi_dbm: float,
    timing_advance: Optional[int] = None,
    radio_type: str = "LTE",
    base_range: Optional[float] = None
) -> float:
    """
    Compute dynamic circular accuracy radius (in meters) representing the geographic
    uncertainty boundary of the cellular signal.

    Strong signal (e.g. -60 dBm) -> tight uncertainty circle (~150m-300m)
    Weak signal (e.g. -115 dBm) -> wide uncertainty circle (~2500m-4000m)
    Timing advance provides hard upper bounds.
    """
    # 1. Distance derived from RF path loss
    rf_distance = compute_path_loss_distance(rssi_dbm)

    # 2. Timing Advance upper bounds if present
    # In LTE, 1 TA step is approximately 78.12 meters.
    # In GSM, 1 TA step is approximately 554 meters.
    ta_bound: Optional[float] = None
    if timing_advance is not None and timing_advance >= 0:
        if "gsm" in radio_type.lower():
            ta_bound = (timing_advance + 1) * 554.0
        else:
            ta_bound = (timing_advance + 1) * 78.12

    # If base range from cell database is known, weight it
    if base_range and base_range > 0:
        # Scale base cell radius with RSSI ratio
        # Nominal RSSI is -85 dBm
        rssi_factor = math.pow(10.0, (-85.0 - rssi_dbm) / 30.0)
        computed_radius = base_range * max(0.25, min(2.5, rssi_factor))
    else:
        # Standard cell coverage radius envelope
        # Add 25% safety margin for multipath fading & non-line-of-sight (NLOS)
        computed_radius = rf_distance * 1.25

    if ta_bound is not None:
        computed_radius = min(computed_radius, ta_bound)

    # Clamp to realistic physical cell boundaries
    clamped_radius = max(
        settings.MIN_ACCURACY_RADIUS_METERS,
        min(settings.MAX_ACCURACY_RADIUS_METERS, computed_radius)
    )

    return round(clamped_radius, 1)


def haversine_distance_meters(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """
    Calculate the great circle distance between two geographic coordinates
    on Earth in meters using the Haversine formula.
    """
    earth_radius_m = 6371000.0  # Earth mean radius in meters

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2)
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return earth_radius_m * c


def forward_geodesic_offset(
    lat: float, lon: float, distance_meters: float, bearing_degrees: float
) -> Tuple[float, float]:
    """
    Calculate destination coordinates given starting point, distance in meters,
    and bearing in degrees.
    """
    earth_radius_m = 6371000.0
    bearing_rad = math.radians(bearing_degrees)
    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)

    dest_lat_rad = math.asin(
        math.sin(lat_rad) * math.cos(distance_meters / earth_radius_m)
        + math.cos(lat_rad)
        * math.sin(distance_meters / earth_radius_m)
        * math.cos(bearing_rad)
    )

    dest_lon_rad = lon_rad + math.atan2(
        math.sin(bearing_rad)
        * math.sin(distance_meters / earth_radius_m)
        * math.cos(lat_rad),
        math.cos(distance_meters / earth_radius_m)
        - math.sin(lat_rad) * math.sin(dest_lat_rad)
    )

    return (
        round(math.degrees(dest_lat_rad), 6),
        round(math.degrees(dest_lon_rad), 6)
    )

