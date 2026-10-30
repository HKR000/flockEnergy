import os
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application configuration settings."""

    # Upstream Portal Configuration
    PORTAL_BASE_URL: str = Field(
        default="https://urja-ops.flockenergy.tech",
        description="Base URL of the upstream Urja Meter Ops portal",
    )
    PORTAL_EMAIL: str = Field(
        default="operator@urja.local",
        description="Urja portal login email / username",
    )
    PORTAL_PASSWORD: str = Field(
        default="urja-ops-2026",
        description="Urja portal login password",
    )

    # Cache & Sync Configuration
    CACHE_TTL_SECONDS: int = Field(
        default=3600,
        description="In-memory cache TTL for full export in seconds (default: 1 hour)",
    )
    SYNC_ON_STARTUP: bool = Field(
        default=True,
        description="Whether to perform an initial hydration sync on startup",
    )
    REQUEST_TIMEOUT_SECONDS: float = Field(
        default=15.0,
        description="HTTP request timeout when contacting upstream portal",
    )

    # API Server Configuration
    API_HOST: str = Field(default="0.0.0.0", description="Host to bind API server")
    API_PORT: int = Field(default=8000, description="Port to bind API server")
    DEBUG: bool = Field(default=False, description="Debug mode")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()
