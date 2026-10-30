import asyncio
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import settings
settings.SYNC_ON_STARTUP = False

from app.models.dt import DistributionTransformer
from app.routers.health import health_check
from app.routers.hierarchy import get_network_hierarchy
from app.routers.meters import get_meter, get_meter_consumption, get_nearby_meters, list_meters
from app.routers.sync import get_sync_status
from app.routers.transformers import get_transformer, list_transformers
from app.services.meter_service import MeterService
from app.services.sync_service import SyncService

sample_raw = [
    {
        "meterId": "J100000",
        "serialNo": "SE33962",
        "make": "HPL",
        "phaseType": "single",
        "installStatus": "Installed",
        "installType": "Whole Current",
        "build": "legacy",
        "dtCode": "DT-001",
        "hierarchy": {
            "zone": {"name": "Jaipur Zone 1", "code": "Z-01"},
            "circle": {"name": "Circle 1", "code": "C-01"},
            "division": {"name": "Division 1", "code": "D-01"},
            "subdivision": {"name": "Subdivision 1", "code": "SD-01"},
            "substation": {"name": "Substation 1", "code": "SS-01"},
            "feeder": {"name": "Feeder 1", "code": "F-001"},
            "dt": {"name": "Malviya Nagar DT 1", "code": "DT-001"},
        },
        "geo": {"lat": 26.9389, "lng": 75.8309},
    },
    {
        "meterId": "J100001",
        "serialNo": "GE84132",
        "make": "Genus",
        "phaseType": "three",
        "installStatus": "Faulty",
        "installType": "CT Operated",
        "build": "v2",
        "dtCode": "DT-002",
        "hierarchy": {
            "zone": {"name": "Jaipur Zone 1", "code": "Z-01"},
            "circle": {"name": "Circle 1", "code": "C-01"},
            "division": {"name": "Division 1", "code": "D-01"},
            "subdivision": {"name": "Subdivision 1", "code": "SD-01"},
            "substation": {"name": "Substation 1", "code": "SS-01"},
            "feeder": {"name": "Feeder 2", "code": "F-002"},
            "dt": {"name": "Mansarovar DT 2", "code": "DT-002"},
        },
        "geo": {"lat": 26.8221, "lng": 75.9071},
    },
]

class MockPortalClient:
    base_url = "https://urja-ops.flockenergy.tech"

    async def check_health(self):
        return True

    async def get_meter_energy(self, meter_id):
        return [
            {"timestamp": "23/06/2026 00:00", "kwh": "100.0", "kvah": "110.0", "voltR": "230.0"},
            {"timestamp": "23/06/2026 00:30", "kwh": "105.0", "kvah": "115.0", "voltR": "232.0"},
        ]

def get_test_sync_service():
    srv = SyncService(MockPortalClient())
    srv._raw_meters = sample_raw
    srv._meters_by_id = {m["meterId"]: m for m in sample_raw}
    srv._summaries = [MeterService.normalize_meter_summary(m) for m in sample_raw]
    srv._transformers = [
        DistributionTransformer(code="DT-001", name="Malviya Nagar DT 1", feeder_code="F-001", capacity_kva=100, connected_meters_count=1),
        DistributionTransformer(code="DT-002", name="Mansarovar DT 2", feeder_code="F-002", capacity_kva=63, connected_meters_count=1),
    ]
    srv._transformers_by_code = {dt.code: dt for dt in srv._transformers}
    srv._last_synced_at = datetime.now(timezone.utc)
    srv._is_syncing = False
    return srv

async def run_api_tests():
    srv = get_test_sync_service()

    # 1. Health
    h = await health_check(service=srv)
    assert h["status"] == "healthy"
    assert h["service"] == "urja-meter-ops-api"
    assert h["upstream_portal"]["reachable"] is True

    # 2. List meters
    meters_resp = await list_meters(service=srv)
    assert meters_resp.total == 2
    assert len(meters_resp.items) == 2

    # 3. Filter by make
    make_resp = await list_meters(make="HPL", service=srv)
    assert make_resp.total == 1
    assert make_resp.items[0].make == "HPL"

    # 4. Filter by status
    status_resp = await list_meters(install_status="Faulty", service=srv)
    assert status_resp.total == 1
    assert status_resp.items[0].meter_id == "J100001"

    # 5. Nearby meters
    nearby = await get_nearby_meters(latitude=26.9389, longitude=75.8309, radius_meters=1000.0, service=srv)
    assert len(nearby) >= 1
    assert nearby[0].meter.meter_id == "J100000"

    # 6. Meter details
    m_detail = await get_meter("J100000", service=srv)
    assert m_detail.meter_id == "J100000"
    assert m_detail.make == "HPL"
    assert m_detail.hierarchy.zone.code == "Z-01"

    # 7. Meter consumption
    cons = await get_meter_consumption("J100000", service=srv)
    assert cons["meter_id"] == "J100000"
    assert cons["summary"].reading_count == 2
    assert cons["summary"].total_consumption_kwh == 5.0

    # 8. Transformers list
    tfs = await list_transformers(service=srv)
    assert tfs.total == 2
    assert tfs.items[0].code == "DT-001"

    # 9. Transformer detail with connected meters
    tf_det = await get_transformer("DT-001", service=srv)
    assert tf_det["transformer"].code == "DT-001"
    assert tf_det["connected_meters_count"] == 1
    assert tf_det["meters"][0].meter_id == "J100000"

    # 10. Hierarchy tree
    tree = await get_network_hierarchy(service=srv)
    assert tree.total_meters == 2
    assert len(tree.zones) == 1

    # 11. Sync status
    s_status = await get_sync_status(service=srv)
    assert s_status.is_fresh is True
    assert s_status.total_meters_cached == 2

    print("All 11 API endpoints tested successfully!")

def test_api_suite():
    asyncio.run(run_api_tests())

if __name__ == "__main__":
    test_api_suite()
