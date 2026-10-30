from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class SyncStatus(BaseModel):
    """Synchronization and cache freshness status."""
    is_syncing: bool = Field(..., description="Whether a background sync is currently running")
    last_synced_at: Optional[datetime] = Field(None, description="Timestamp of the last successful sync")
    seconds_since_last_sync: Optional[float] = Field(None, description="Age of current cache in seconds")
    ttl_seconds: int = Field(..., description="Configured cache TTL in seconds")
    is_fresh: bool = Field(..., description="Whether cache is within TTL")
    total_meters_cached: int = Field(..., description="Number of meters currently indexed in memory")
    total_transformers_cached: int = Field(..., description="Number of DTs currently indexed in memory")
    error: Optional[str] = Field(None, description="Last sync error message if any")
