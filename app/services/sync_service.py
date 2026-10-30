import asyncio
from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from app.client.portal_client import PortalClient
from app.config import settings
from app.models.common import PaginatedResponse
from app.models.dt import DistributionTransformer
from app.models.meter import MeterDetail, MeterSummary
from app.models.sync import SyncStatus
from app.services.meter_service import MeterService

logger = logging.getLogger(__name__)


class SyncService:
    """Manages local indexing, synchronization with the Urja portal, and fast querying."""

    def __init__(self, portal_client: PortalClient):
        self.client = portal_client
        self._raw_meters: List[Dict[str, Any]] = []
        self._summaries: List[MeterSummary] = []
        self._meters_by_id: Dict[str, Dict[str, Any]] = {}
        self._transformers: List[DistributionTransformer] = []
        self._transformers_by_code: Dict[str, DistributionTransformer] = {}
        self._last_synced_at: Optional[datetime] = None
        self._is_syncing: bool = False
        self._sync_error: Optional[str] = None
        self._lock: Optional[asyncio.Lock] = None

    def _get_lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    @property
    def is_fresh(self) -> bool:
        """Check if cached dataset is within the configured TTL."""
        if not self._last_synced_at or not self._raw_meters:
            return False
        age_seconds = (datetime.now(timezone.utc) - self._last_synced_at).total_seconds()
        return age_seconds < settings.CACHE_TTL_SECONDS

    def get_status(self) -> SyncStatus:
        """Return the current sync and cache status."""
        age = None
        if self._last_synced_at:
            age = (datetime.now(timezone.utc) - self._last_synced_at).total_seconds()

        return SyncStatus(
            is_syncing=self._is_syncing,
            last_synced_at=self._last_synced_at,
            seconds_since_last_sync=round(age, 1) if age is not None else None,
            ttl_seconds=settings.CACHE_TTL_SECONDS,
            is_fresh=self.is_fresh,
            total_meters_cached=len(self._raw_meters),
            total_transformers_cached=len(self._transformers),
            error=self._sync_error,
        )

    async def sync(self, force: bool = False) -> SyncStatus:
        """Synchronize local cache and indexes from upstream portal via signed export."""
        async with self._get_lock():
            if self._is_syncing:
                return self.get_status()

            if self.is_fresh and not force:
                logger.info("Local index is still fresh (age < %ds). Skipping sync.", settings.CACHE_TTL_SECONDS)
                return self.get_status()

            self._is_syncing = True
            self._sync_error = None
            logger.info("Starting dataset synchronization from Urja portal...")

            try:
                # 1. Fetch all meters via signed export
                raw_meters = await self.client.export_all_meters()
                logger.info("Successfully exported %d meters from portal", len(raw_meters))

                # 2. Fetch all transformers
                raw_dts = await self.client.get_all_transformers()
                logger.info("Successfully fetched %d transformers from portal", len(raw_dts))

                # 3. Index meters and count per DT
                meter_counts_by_dt: Dict[str, int] = {}
                meters_by_id: Dict[str, Dict[str, Any]] = {}
                summaries: List[MeterSummary] = []

                for m in raw_meters:
                    mid = m.get("meterId") or ""
                    meters_by_id[mid] = m
                    summary = MeterService.normalize_meter_summary(m)
                    summaries.append(summary)

                    dt_code = summary.dt_code
                    if dt_code:
                        meter_counts_by_dt[dt_code] = meter_counts_by_dt.get(dt_code, 0) + 1

                # 4. Transform and index transformers
                transformers: List[DistributionTransformer] = []
                transformers_by_code: Dict[str, DistributionTransformer] = {}

                for dt in raw_dts:
                    code = dt.get("code") or ""
                    model = DistributionTransformer(
                        code=code,
                        name=dt.get("name") or code,
                        feeder_code=dt.get("feederCode") or "",
                        capacity_kva=int(dt.get("capacityKva") or 0),
                        connected_meters_count=meter_counts_by_dt.get(code, 0),
                    )
                    transformers.append(model)
                    transformers_by_code[code] = model

                # Atomic swap
                self._raw_meters = raw_meters
                self._summaries = summaries
                self._meters_by_id = meters_by_id
                self._transformers = transformers
                self._transformers_by_code = transformers_by_code
                self._last_synced_at = datetime.now(timezone.utc)
                logger.info("Index updated with %d meters and %d transformers", len(raw_meters), len(transformers))

            except Exception as e:
                logger.error("Sync failed: %s", e, exc_info=True)
                self._sync_error = str(e)
            finally:
                self._is_syncing = False

            return self.get_status()

    async def ensure_synced(self):
        """Ensure dataset is populated; triggers sync if empty or stale."""
        if not self._raw_meters or not self.is_fresh:
            await self.sync()

    def get_raw_meters(self) -> List[Dict[str, Any]]:
        return self._raw_meters

    def get_all_summaries(self) -> List[MeterSummary]:
        return self._summaries

    def get_meter_by_id(self, meter_id: str) -> Optional[MeterDetail]:
        raw = self._meters_by_id.get(meter_id)
        if not raw:
            return None
        return MeterService.normalize_meter_detail(raw)

    def query_meters(
        self,
        query: Optional[str] = None,
        make: Optional[str] = None,
        phase_type: Optional[str] = None,
        install_status: Optional[str] = None,
        install_type: Optional[str] = None,
        build: Optional[str] = None,
        dt_code: Optional[str] = None,
        feeder_code: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedResponse[MeterSummary]:
        """Powerful local query layer supporting multi-attribute filtering not possible on the portal."""
        if not isinstance(page, int):
            page = getattr(page, "default", 1)
        if not isinstance(page_size, int):
            page_size = getattr(page_size, "default", 20)
        page = max(1, page)
        page_size = max(1, page_size)

        filtered = self._summaries

        if query and isinstance(query, str):
            q_lower = query.strip().lower()
            filtered = [
                m for m in filtered
                if q_lower in m.meter_id.lower()
                or q_lower in m.serial_no.lower()
                or q_lower in m.make.lower()
                or (m.dt_code and q_lower in m.dt_code.lower())
                or (m.dt_name and q_lower in m.dt_name.lower())
                or (m.feeder_code and q_lower in m.feeder_code.lower())
            ]

        if make and isinstance(make, str):
            m_lower = make.strip().lower()
            filtered = [m for m in filtered if m.make.lower() == m_lower]

        if phase_type and isinstance(phase_type, str):
            p_lower = phase_type.strip().lower()
            filtered = [m for m in filtered if m.phase_type.lower() == p_lower]

        if install_status and isinstance(install_status, str):
            s_lower = install_status.strip().lower()
            filtered = [m for m in filtered if m.install_status.lower() == s_lower]

        if install_type and isinstance(install_type, str):
            it_lower = install_type.strip().lower()
            filtered = [m for m in filtered if m.install_type and m.install_type.lower() == it_lower]

        if build and isinstance(build, str):
            b_lower = build.strip().lower()
            filtered = [m for m in filtered if m.build and m.build.lower() == b_lower]

        if dt_code and isinstance(dt_code, str):
            dt_upper = dt_code.strip().upper()
            filtered = [m for m in filtered if m.dt_code and m.dt_code.upper() == dt_upper]

        if feeder_code and isinstance(feeder_code, str):
            f_upper = feeder_code.strip().upper()
            filtered = [m for m in filtered if m.feeder_code and m.feeder_code.upper() == f_upper]

        total = len(filtered)
        total_pages = (total + page_size - 1) // page_size if total > 0 else 0
        start = (page - 1) * page_size
        end = start + page_size
        page_items = filtered[start:end]

        return PaginatedResponse(
            items=page_items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    def query_transformers(
        self,
        feeder_code: Optional[str] = None,
        min_capacity: Optional[int] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedResponse[DistributionTransformer]:
        """Query distribution transformers with optional feeder filtering."""
        if not isinstance(page, int):
            page = getattr(page, "default", 1)
        if not isinstance(page_size, int):
            page_size = getattr(page_size, "default", 20)
        page = max(1, page)
        page_size = max(1, page_size)

        filtered = self._transformers

        if feeder_code and isinstance(feeder_code, str):
            f_upper = feeder_code.strip().upper()
            filtered = [dt for dt in filtered if dt.feeder_code.upper() == f_upper]

        if min_capacity is not None and isinstance(min_capacity, (int, float)):
            filtered = [dt for dt in filtered if dt.capacity_kva >= min_capacity]

        total = len(filtered)
        total_pages = (total + page_size - 1) // page_size if total > 0 else 0
        start = (page - 1) * page_size
        end = start + page_size
        page_items = filtered[start:end]

        return PaginatedResponse(
            items=page_items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    def get_transformer_by_code(self, code: str) -> Optional[DistributionTransformer]:
        return self._transformers_by_code.get(code.strip().upper())
