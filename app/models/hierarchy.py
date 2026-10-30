from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class HierarchyTreeNode(BaseModel):
    """Hierarchical node in the electrical distribution tree."""
    level: str = Field(..., description="Level in hierarchy ('zone', 'circle', 'division', 'subdivision', 'substation', 'feeder', 'dt', 'meter')")
    name: str = Field(..., description="Node display name")
    code: str = Field(..., description="Unique node code")
    meter_count: int = Field(default=0, description="Total meters subordinate to this node")
    children: List["HierarchyTreeNode"] = Field(
        default_factory=list, description="Subordinate child nodes"
    )


class NetworkHierarchyResponse(BaseModel):
    """Root network hierarchy representation."""
    utility_name: str = Field(default="Urja Power Distribution", description="Utility name")
    total_meters: int = Field(..., description="Total meters categorized in tree")
    zones: List[HierarchyTreeNode] = Field(..., description="Top-level utility zones")
