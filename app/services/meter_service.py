import logging
from typing import Any, Dict, List, Optional
from app.models.common import GeoCoordinates
from app.models.meter import (
    ConsumptionSummary,
    EnergyReading,
    HierarchyLevel,
    MeterDetail,
    MeterHierarchy,
    MeterSummary,
)

logger = logging.getLogger(__name__)


def parse_float_safe(val: Any) -> Optional[float]:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


class MeterService:
    """Business logic for meter normalization, calculations, and consumption summaries."""

    @staticmethod
    def normalize_meter_summary(raw: Dict[str, Any]) -> MeterSummary:
        """Convert raw portal JSON (from export or search) into normalized MeterSummary."""
        meter_id = raw.get("meterId") or raw.get("meter_id") or ""
        serial_no = raw.get("serialNo") or raw.get("serial_no") or ""
        make = raw.get("make") or "Unknown"
        phase_type = raw.get("phaseType") or raw.get("phase_type") or "unknown"
        install_status = raw.get("installStatus") or raw.get("install_status") or "Unknown"
        install_type = raw.get("installType") or raw.get("install_type")
        build = raw.get("build")
        dt_code = raw.get("dtCode") or raw.get("dt_code")

        hierarchy = raw.get("hierarchy") or {}
        dt_info = hierarchy.get("dt") or {}
        dt_name = dt_info.get("name") if isinstance(dt_info, dict) else None
        feeder_info = hierarchy.get("feeder") or {}
        feeder_code = feeder_info.get("code") if isinstance(feeder_info, dict) else None

        coords = None
        geo = raw.get("geo") or {}
        lat = parse_float_safe(geo.get("lat") or geo.get("latitude"))
        lng = parse_float_safe(geo.get("lng") or geo.get("longitude"))
        if lat is not None and lng is not None:
            coords = GeoCoordinates(latitude=lat, longitude=lng)

        return MeterSummary(
            meter_id=meter_id,
            serial_no=serial_no,
            make=make,
            phase_type=phase_type,
            install_status=install_status,
            install_type=install_type,
            build=build,
            dt_code=dt_code,
            dt_name=dt_name,
            feeder_code=feeder_code,
            coordinates=coords,
        )

    @staticmethod
    def normalize_hierarchy(raw_hierarchy: Dict[str, Any]) -> MeterHierarchy:
        """Normalize raw hierarchy dictionary to strongly typed MeterHierarchy."""
        if not raw_hierarchy:
            return MeterHierarchy()

        def parse_node(node: Any) -> Optional[HierarchyLevel]:
            if not isinstance(node, dict):
                return None
            name = node.get("name")
            code = node.get("code")
            if name and code:
                return HierarchyLevel(name=name, code=code)
            return None

        return MeterHierarchy(
            zone=parse_node(raw_hierarchy.get("zone")),
            circle=parse_node(raw_hierarchy.get("circle")),
            division=parse_node(raw_hierarchy.get("division")),
            subdivision=parse_node(raw_hierarchy.get("subdivision")),
            substation=parse_node(raw_hierarchy.get("substation")),
            feeder=parse_node(raw_hierarchy.get("feeder")),
            dt=parse_node(raw_hierarchy.get("dt")),
        )

    @staticmethod
    def normalize_meter_detail(raw: Dict[str, Any]) -> MeterDetail:
        """Produce full MeterDetail model with normalized nameplate and hierarchy."""
        summary = MeterService.normalize_meter_summary(raw)
        hierarchy = MeterService.normalize_hierarchy(raw.get("hierarchy") or {})

        # Build nameplate attributes dictionary
        nameplate = {
            "Meter ID": summary.meter_id,
            "Serial Number": summary.serial_no,
            "Manufacturer": summary.make,
            "Phase Configuration": summary.phase_type,
            "Installation Status": summary.install_status,
        }
        if summary.install_type:
            nameplate["Installation Type"] = summary.install_type
        if summary.build:
            nameplate["Telemetry Generation"] = summary.build
        if summary.dt_code:
            nameplate["Distribution Transformer"] = f"{summary.dt_name or ''} ({summary.dt_code})".strip()
        if summary.feeder_code:
            nameplate["Feeder"] = summary.feeder_code

        return MeterDetail(
            **summary.model_dump(),
            hierarchy=hierarchy,
            nameplate_attributes=nameplate,
            latest_reading=None,
        )

    @staticmethod
    def normalize_energy_reading(raw: Dict[str, Any]) -> EnergyReading:
        """Parse raw energy reading object."""
        return EnergyReading(
            timestamp=str(raw.get("timestamp", "")),
            kwh=parse_float_safe(raw.get("kwh")),
            kvah=parse_float_safe(raw.get("kvah")),
            volt_r=parse_float_safe(raw.get("voltR") or raw.get("volt_r")),
        )

    @staticmethod
    def calculate_consumption_summary(readings: List[EnergyReading]) -> ConsumptionSummary:
        """Compute statistical summary across energy reading intervals."""
        if not readings:
            return ConsumptionSummary(
                reading_count=0,
                start_time=None,
                end_time=None,
                start_kwh=None,
                end_kwh=None,
                total_consumption_kwh=None,
                avg_voltage=None,
                min_voltage=None,
                max_voltage=None,
            )

        start_time = readings[0].timestamp
        end_time = readings[-1].timestamp

        kwh_values = [r.kwh for r in readings if r.kwh is not None]
        start_kwh = kwh_values[0] if kwh_values else None
        end_kwh = kwh_values[-1] if kwh_values else None
        total_delta = round(end_kwh - start_kwh, 2) if (start_kwh is not None and end_kwh is not None) else None

        voltages = [r.volt_r for r in readings if r.volt_r is not None]
        avg_volt = round(sum(voltages) / len(voltages), 1) if voltages else None
        min_volt = min(voltages) if voltages else None
        max_volt = max(voltages) if voltages else None

        return ConsumptionSummary(
            reading_count=len(readings),
            start_time=start_time,
            end_time=end_time,
            start_kwh=start_kwh,
            end_kwh=end_kwh,
            total_consumption_kwh=total_delta,
            avg_voltage=avg_volt,
            min_voltage=min_volt,
            max_voltage=max_volt,
        )
