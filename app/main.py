import asyncio
from contextlib import asynccontextmanager
import logging
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.client.portal_client import PortalClient
from app.config import settings
from app.routers import health, hierarchy, meters, sync, transformers
from app.services.sync_service import SyncService

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("urja_api")

# Singleton client and service instances
portal_client = PortalClient(
    base_url=settings.PORTAL_BASE_URL,
    email=settings.PORTAL_EMAIL,
    password=settings.PORTAL_PASSWORD,
    timeout=settings.REQUEST_TIMEOUT_SECONDS,
)
sync_service = SyncService(portal_client)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle events: startup hydration and client teardown."""
    logger.info("Initializing Urja Meter Ops Gateway...")
    if settings.SYNC_ON_STARTUP:
        logger.info("Scheduling startup synchronization from Urja portal in background...")
        asyncio.create_task(sync_service.sync())

    yield

    logger.info("Shutting down Urja Meter Ops Gateway...")
    await portal_client.close()


app = FastAPI(
    title="Urja Meter Ops Gateway API",
    description=(
        "Production-grade integration service and query gateway over the Urja Meter Ops portal. "
        "Provides normalized meter models, multi-attribute querying, spatial proximity search, "
        "network hierarchy reconstruction, interval consumption analytics, and background caching."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Enable CORS for programmatic consumers and external frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers
app.include_router(meters.router)
app.include_router(transformers.router)
app.include_router(hierarchy.router)
app.include_router(sync.router)
app.include_router(health.router)

# Mount static files and serve dashboard
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", include_in_schema=False)
@app.get("/dashboard", include_in_schema=False)
async def serve_dashboard():
    """Serve the modern interactive web client dashboard."""
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Urja Meter Ops Gateway API. Visit /docs for OpenAPI documentation."}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.API_HOST, port=settings.API_PORT, reload=settings.DEBUG)
