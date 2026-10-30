from fastapi import APIRouter, Depends
from app.models.hierarchy import NetworkHierarchyResponse
from app.services.network_service import NetworkService
from app.services.sync_service import SyncService

router = APIRouter(prefix="/api/v1/hierarchy", tags=["Hierarchy"])


def get_sync_service() -> SyncService:
    from app.main import sync_service
    return sync_service


@router.get(
    "",
    response_model=NetworkHierarchyResponse,
    summary="Get Network Hierarchy Tree",
    description=(
        "Reconstructs the full utility network topology tree: "
        "Zone -> Circle -> Division -> Subdivision -> Substation -> Feeder -> DT -> Meters. "
        "Provides roll-up meter counts at every structural level."
    ),
)
async def get_network_hierarchy(
    service: SyncService = Depends(get_sync_service),
):
    await service.ensure_synced()
    raw_meters = service.get_raw_meters()
    return NetworkService.build_hierarchy_tree(raw_meters)
