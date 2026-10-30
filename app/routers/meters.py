from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from app.models.common import GeoCoordinates, PaginatedResponse
from app.models.meter import ConsumptionSummary, EnergyReading, MeterDetail, MeterSummary, NearbyMeter
from app.services.geo_service import GeoService
from app.services.meter_service import MeterService
from app.services.sync_service import SyncService

router = APIRouter(prefix="/api/v1/meters", tags=["Meters"])


# Dependency to get sync_service from app state
def get_sync_service() -> SyncService:
    from app.main import sync_service
    return sync_service


@router.get(
    "",
    response_model=PaginatedResponse[MeterSummary],
    summary="List & Filter Smart Meters",
    description=(
        "Query smart meters across multiple attributes. Unlike the legacy portal which only "
        "searches meterId and serialNo, this endpoint allows filtering by make, phase, status, "
        "build, DT code, and feeder."
    ),
)
async def list_meters(
    q: Optional[str] = Query(None, description="Free-text search across meterId, serialNo, make, DT, feeder"),
    make: Optional[str] = Query(None, description="Filter by manufacturer (e.g. 'HPL', 'Genus', 'L&T')"),
    phase_type: Optional[str] = Query(None, description="Filter by phase ('single' or 'three')"),
    install_status: Optional[str] = Query(None, description="Filter by status ('Installed', 'Faulty', 'Decommissioned')"),
    install_type: Optional[str] = Query(None, description="Filter by installation type ('Whole Current', 'CT Operated')"),
    build: Optional[str] = Query(None, description="Filter by telemetry generation ('legacy' or 'v2')"),
    dt_code: Optional[str] = Query(None, description="Filter by Distribution Transformer code (e.g. 'DT-001')"),
    feeder_code: Optional[str] = Query(None, description="Filter by Feeder code (e.g. 'F-001')"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=500, description="Items per page"),
    service: SyncService = Depends(get_sync_service),
):
    await service.ensure_synced()
    return service.query_meters(
        query=q,
        make=make,
        phase_type=phase_type,
        install_status=install_status,
        install_type=install_type,
        build=build,
        dt_code=dt_code,
        feeder_code=feeder_code,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/nearby",
    response_model=List[NearbyMeter],
    summary="Find Meters Near Location",
    description="Spatial proximity search returning meters within a given radius (in meters) of (lat, lng).",
)
async def get_nearby_meters(
    latitude: float = Query(..., description="Target latitude (e.g. 26.9124)"),
    longitude: float = Query(..., description="Target longitude (e.g. 75.7873)"),
    radius_meters: float = Query(5000.0, ge=10.0, le=100000.0, description="Radius in meters (default 5000m)"),
    limit: int = Query(50, ge=1, le=500, description="Maximum number of nearby meters to return"),
    service: SyncService = Depends(get_sync_service),
):
    await service.ensure_synced()
    all_meters = service.get_all_summaries()
    return GeoService.find_nearby_meters(
        meters=all_meters,
        latitude=latitude,
        longitude=longitude,
        radius_meters=radius_meters,
        limit=limit,
    )


@router.get(
    "/{meter_id}",
    response_model=MeterDetail,
    summary="Get Meter Details",
    description="Fetch complete meter record including normalized nameplate attributes, hierarchy path, and coordinates.",
)
async def get_meter(
    meter_id: str,
    service: SyncService = Depends(get_sync_service),
):
    await service.ensure_synced()
    meter = service.get_meter_by_id(meter_id)
    if not meter:
        raise HTTPException(status_code=404, detail=f"Meter '{meter_id}' not found.")
    return meter


@router.get(
    "/{meter_id}/consumption",
    summary="Get Meter Consumption & Readings",
    description=(
        "Retrieve interval consumption readings (kWh, kVAh, voltage) directly from the portal, "
        "accompanied by computed consumption delta and voltage stability metrics."
    ),
)
async def get_meter_consumption(
    meter_id: str,
    service: SyncService = Depends(get_sync_service),
):
    await service.ensure_synced()
    meter = service.get_meter_by_id(meter_id)
    if not meter:
        raise HTTPException(status_code=404, detail=f"Meter '{meter_id}' not found.")

    raw_readings = await service.client.get_meter_energy(meter_id)
    readings = [MeterService.normalize_energy_reading(r) for r in raw_readings]
    summary = MeterService.calculate_consumption_summary(readings)

    return {
        "meter_id": meter_id,
        "summary": summary,
        "readings": readings,
    }


@router.get(
    "/{meter_id}/geo",
    response_model=GeoCoordinates,
    summary="Get Meter Geolocation",
    description="Retrieve geographic coordinates for a meter.",
)
async def get_meter_geo(
    meter_id: str,
    service: SyncService = Depends(get_sync_service),
):
    await service.ensure_synced()
    meter = service.get_meter_by_id(meter_id)
    if not meter:
        raise HTTPException(status_code=404, detail=f"Meter '{meter_id}' not found.")
    if not meter.coordinates:
        raise HTTPException(status_code=404, detail=f"Coordinates unavailable for meter '{meter_id}'.")
    return meter.coordinates
