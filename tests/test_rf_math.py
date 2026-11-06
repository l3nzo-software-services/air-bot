"""
Unit tests for RF propagation, path loss, and accuracy radius calculations.
"""

import pytest
from cellsentinel.services.rf_math import (
    compute_path_loss_distance,
    compute_accuracy_radius,
    haversine_distance_meters,
    forward_geodesic_offset
)


def test_path_loss_distance():
    # Strong signal close to tower antenna (-50 dBm with -42 dBm ref -> PL = 8 dB)
    dist_strong = compute_path_loss_distance(-50.0, reference_power_dbm=-42.0, path_loss_exponent=3.0)
    assert dist_strong < 5.0  # Under 5 meters

    # Medium signal (-82 dBm with -42 dBm ref -> PL = 40 dB -> 10^(4/3) = ~21.5m)
    dist_med = compute_path_loss_distance(-82.0, reference_power_dbm=-42.0, path_loss_exponent=3.0)
    assert 15.0 < dist_med < 30.0

    # Weak signal at cell edge (-115 dBm with -42 dBm ref -> PL = 73 dB -> 10^(7.3/3) = ~270m)
    dist_weak = compute_path_loss_distance(-115.0, reference_power_dbm=-42.0, path_loss_exponent=3.0)
    assert dist_weak > 200.0
    assert dist_weak > dist_med


def test_accuracy_radius_dynamics():
    # Strong signal produces tighter radius
    radius_strong = compute_accuracy_radius(rssi_dbm=-60.0)
    # Weak signal produces wider radius
    radius_weak = compute_accuracy_radius(rssi_dbm=-110.0)

    assert radius_strong < radius_weak
    assert radius_strong >= 120.0  # Clamped to minimum configured bound
    assert radius_weak <= 4500.0   # Clamped to maximum configured bound


def test_timing_advance_clamp():
    # Timing advance of 1 in LTE bounds radius to ~156 meters
    radius_ta = compute_accuracy_radius(rssi_dbm=-115.0, timing_advance=1, radio_type="LTE")
    assert radius_ta <= 160.0


def test_haversine_distance():
    # Distance between Connaught Place (28.6315, 77.2167) and Mandi House (28.6412, 77.2248)
    dist = haversine_distance_meters(28.6315, 77.2167, 28.6412, 77.2248)
    assert 1000.0 < dist < 2000.0  # ~1.3 km


def test_forward_geodesic():
    lat, lon = forward_geodesic_offset(28.6315, 77.2167, 1000.0, 90.0)
    # Moving east should increase longitude while keeping latitude roughly constant
    assert lon > 77.2167
    assert abs(lat - 28.6315) < 0.01
