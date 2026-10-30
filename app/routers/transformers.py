from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from app.models.common import PaginatedResponse
from app.models.dt import DistributionTransformer
from app.models.meter import MeterSummary
from app.services.sync_service import SyncService

router = APIRouter(prefix="/api/v1/transformers", tags=["Transformers"])


def get_sync_service() -> SyncService:
    from app.main import sync_service
    return sync_service


@router.get(
    "",
    response_model=PaginatedResponse[DistributionTransformer],
    summary="List Distribution Transformers",
    description="List and paginate all DTs with connected meter counts and capacity.",
)
async def list_transformers(
    feeder_code: Optional[str] = Query(None, description="Filter by feeder code (e.g. 'F-001')"),
    min_capacity: Optional[int] = Query(None, ge=0, description="Minimum transformer capacity in kVA"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    service: SyncService = Depends(get_sync_service),
):
    await service.ensure_synced()
    return service.query_transformers(
        feeder_code=feeder_code,
        min_capacity=min_capacity,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{code}",
    summary="Get Transformer Details with Connected Meters",
    description="Retrieve a Distribution Transformer by code along with its list of connected meters.",
)
async def get_transformer(
    code: str,
    service: SyncService = Depends(get_sync_service),
):
    await service.ensure_synced()
    dt = service.get_transformer_by_code(code)
    if not dt:
        raise HTTPException(status_code=404, detail=f"Transformer '{code}' not found.")

    # Find connected meters
    connected = [m for m in service.get_all_summaries() if m.dt_code and m.dt_code.upper() == code.upper()]

    return {
        "transformer": dt,
        "connected_meters_count": len(connected),
        "meters": connected,
    }
