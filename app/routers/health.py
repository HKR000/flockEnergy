from fastapi import APIRouter, Depends
from app.services.sync_service import SyncService

router = APIRouter(prefix="/api/v1/health", tags=["Health"])


def get_sync_service() -> SyncService:
    from app.main import sync_service
    return sync_service


@router.get(
    "",
    summary="Health & Upstream Status",
    description="Check API service health and upstream Urja portal connectivity.",
)
async def health_check(
    service: SyncService = Depends(get_sync_service),
):
    upstream_ok = await service.client.check_health()
    sync_status = service.get_status()

    return {
        "status": "healthy" if upstream_ok else "degraded",
        "service": "urja-meter-ops-api",
        "upstream_portal": {
            "reachable": upstream_ok,
            "url": service.client.base_url,
        },
        "cache": {
            "is_fresh": sync_status.is_fresh,
            "meters_cached": sync_status.total_meters_cached,
            "transformers_cached": sync_status.total_transformers_cached,
            "last_synced_at": sync_status.last_synced_at,
        },
    }
