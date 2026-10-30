from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from app.models.common import GeoCoordinates


class HierarchyLevel(BaseModel):
    """A node in the utility grid hierarchy."""
    name: str = Field(..., description="Entity name (e.g. 'Jaipur Zone 1')")
    code: str = Field(..., description="Unique entity code (e.g. 'Z-01')")


class MeterHierarchy(BaseModel):
    """Complete network placement for a meter."""
    zone: Optional[HierarchyLevel] = Field(None, description="Administrative Zone")
    circle: Optional[HierarchyLevel] = Field(None, description="Distribution Circle")
    division: Optional[HierarchyLevel] = Field(None, description="Operational Division")
    subdivision: Optional[HierarchyLevel] = Field(None, description="Subdivision")
    substation: Optional[HierarchyLevel] = Field(None, description="Electrical Substation")
    feeder: Optional[HierarchyLevel] = Field(None, description="Distribution Feeder line")
    dt: Optional[HierarchyLevel] = Field(None, description="Distribution Transformer (DT)")


class EnergyReading(BaseModel):
    """A single interval consumption reading from the smart meter."""
    timestamp: str = Field(..., description="Timestamp string formatted as DD/MM/YYYY HH:MM")
    kwh: Optional[float] = Field(None, description="Cumulative active energy in kWh")
    kvah: Optional[float] = Field(None, description="Cumulative apparent energy in kVAh")
    volt_r: Optional[float] = Field(None, description="R-phase voltage in Volts")


class ConsumptionSummary(BaseModel):
    """Computed statistics across available energy readings."""
    reading_count: int = Field(..., description="Total readings retrieved")
    start_time: Optional[str] = Field(None, description="Earliest reading timestamp")
    end_time: Optional[str] = Field(None, description="Latest reading timestamp")
    start_kwh: Optional[float] = Field(None, description="Initial kWh reading")
    end_kwh: Optional[float] = Field(None, description="Final kWh reading")
    total_consumption_kwh: Optional[float] = Field(None, description="Net consumption (end - start)")
    avg_voltage: Optional[float] = Field(None, description="Average voltage observed")
    min_voltage: Optional[float] = Field(None, description="Minimum voltage observed")
    max_voltage: Optional[float] = Field(None, description="Maximum voltage observed")


class MeterSummary(BaseModel):
    """Compact summary of a meter for tabular and list endpoints."""
    meter_id: str = Field(..., description="Unique meter identifier, e.g. 'J100000'")
    serial_no: str = Field(..., description="Hardware manufacturer serial number")
    make: str = Field(..., description="Manufacturer (e.g. 'HPL', 'Genus', 'L&T')")
    phase_type: str = Field(..., description="Phase configuration ('single' or 'three')")
    install_status: str = Field(..., description="Status ('Installed', 'Faulty', 'Decommissioned')")
    install_type: Optional[str] = Field(None, description="Installation type ('Whole Current', 'CT Operated')")
    build: Optional[str] = Field(None, description="Underlying portal telemetry model ('legacy' or 'v2')")
    dt_code: Optional[str] = Field(None, description="Connected Distribution Transformer code")
    dt_name: Optional[str] = Field(None, description="Connected Distribution Transformer name")
    feeder_code: Optional[str] = Field(None, description="Connected Feeder code")
    coordinates: Optional[GeoCoordinates] = Field(None, description="Geographic coordinates")


class MeterDetail(MeterSummary):
    """Comprehensive meter detail including nameplate parameters and network hierarchy."""
    hierarchy: Optional[MeterHierarchy] = Field(None, description="Full electrical network path")
    nameplate_attributes: Dict[str, str] = Field(
        default_factory=dict,
        description="Key-value nameplate attributes normalized from portal (handles both legacy and v2)",
    )
    latest_reading: Optional[EnergyReading] = Field(None, description="Most recent energy reading available")


class NearbyMeter(BaseModel):
    """Meter summary returned from spatial proximity queries with calculated distance."""
    meter: MeterSummary = Field(..., description="Meter summary data")
    distance_meters: float = Field(..., description="Distance in meters from requested coordinates")
    distance_km: float = Field(..., description="Distance in kilometers")
