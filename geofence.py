"""Haversine distance for server-side geofence checks (login)."""

import math


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in meters between two WGS84 points."""
    r = 6371000.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = (
        math.sin(dp / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


def within_radius(
    user_lat: float,
    user_lon: float,
    center_lat: float,
    center_lon: float,
    radius_m: float,
) -> bool:
    return haversine_m(user_lat, user_lon, center_lat, center_lon) <= radius_m
