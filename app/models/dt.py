from typing import List, Optional
from pydantic import BaseModel, Field


class DistributionTransformer(BaseModel):
    """Distribution Transformer entity from utility network."""
    code: str = Field(..., description="Unique DT code, e.g. 'DT-001'")
    name: str = Field(..., description="DT descriptive name, e.g. 'Malviya Nagar DT 1'")
    feeder_code: str = Field(..., description="Associated feeder code, e.g. 'F-001'")
    capacity_kva: int = Field(..., description="Transformer rating in kVA, e.g. 100")
    connected_meters_count: Optional[int] = Field(
        None, description="Number of active meters connected to this DT"
    )
