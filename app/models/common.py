from typing import Generic, List, Optional, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard paginated envelope for list endpoints."""
    items: List[T] = Field(..., description="List of items for current page")
    total: int = Field(..., description="Total number of items matching query")
    page: int = Field(..., ge=1, description="Current page number (1-based)")
    page_size: int = Field(..., ge=1, description="Number of items per page")
    total_pages: int = Field(..., ge=0, description="Total number of pages available")


class GeoCoordinates(BaseModel):
    """Geographical coordinate pair."""
    latitude: float = Field(..., description="Latitude coordinate in decimal degrees")
    longitude: float = Field(..., description="Longitude coordinate in decimal degrees")
