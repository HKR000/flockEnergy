import math
from typing import List, Optional, Tuple
from app.models.meter import MeterSummary, NearbyMeter


def haversine_distance_meters(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """Calculate the great-circle distance between two points in meters using the Haversine formula."""
    R = 6371000.0  # Earth's radius in meters

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    return R * c


class GeoService:
    """Geospatial query service for meters."""

    @staticmethod
    def find_nearby_meters(
        meters: List[MeterSummary],
        latitude: float,
        longitude: float,
        radius_meters: float = 5000.0,
        limit: int = 50,
    ) -> List[NearbyMeter]:
        """Find meters within `radius_meters` of (latitude, longitude), sorted by distance."""
        if not isinstance(limit, int):
            limit = getattr(limit, "default", 50)
        if not isinstance(radius_meters, (int, float)):
            radius_meters = getattr(radius_meters, "default", 5000.0)

        results: List[NearbyMeter] = []

        for m in meters:
            if not m.coordinates:
                continue
            dist = haversine_distance_meters(
                latitude, longitude, m.coordinates.latitude, m.coordinates.longitude
            )
            if dist <= radius_meters:
                results.append(
                    NearbyMeter(
                        meter=m,
                        distance_meters=round(dist, 2),
                        distance_km=round(dist / 1000.0, 3),
                    )
                )

        results.sort(key=lambda x: x.distance_meters)
        return results[:limit]
