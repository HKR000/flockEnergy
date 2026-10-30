from fastapi import APIRouter, Depends, Query
from app.models.sync import SyncStatus
from app.services.sync_service import SyncService

router = APIRouter(prefix="/api/v1/sync", tags=["Sync & Cache"])


def get_sync_service() -> SyncService:
    from app.main import sync_service
    return sync_service


@router.get(
    "/status",
    response_model=SyncStatus,
    summary="Get Cache & Sync Freshness Status",
    description="Inspect in-memory cache status, last sync timestamp, TTL, and cached item counts.",
)
async def get_sync_status(
    service: SyncService = Depends(get_sync_service),
):
    return service.get_status()


@router.post(
    "",
    response_model=SyncStatus,
    summary="Trigger On-Demand Sync",
    description="Manually trigger a full signed export sync from the Urja portal to refresh local cache.",
)
async def trigger_sync(
    force: bool = Query(True, description="Force sync even if cache is still fresh"),
    service: SyncService = Depends(get_sync_service),
):
    return await service.sync(force=force)
