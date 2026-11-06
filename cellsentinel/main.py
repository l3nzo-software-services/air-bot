"""
CellSentinel - Main Application Entrypoint.
FastAPI application mounting modular routers, lifecycle hooks, and dashboard templates.
"""

from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse

from cellsentinel.config import settings
from cellsentinel.database import init_db
from cellsentinel.api import devices, telemetry, dashboard


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown hooks."""
    # Initialize SQLite schema & load verified local tower fixtures
    init_db()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    description="Cell-Tower Telemetry Ingestion & OpenCellID Geolocation Engine",
    version=settings.APP_VERSION,
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Modular Routers
app.include_router(devices.router)
app.include_router(telemetry.router)
app.include_router(dashboard.router)


@app.get("/health", tags=["Health"])
def health_check():
    """System health verification check."""
    return {
        "status": "ONLINE",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "database": "CONNECTED"
    }


@app.get("/", response_class=HTMLResponse, tags=["Dashboard"])
def get_dashboard_view():
    """Serve the primary Leaflet.js interactive web dashboard."""
    template_path = Path(__file__).parent / "templates" / "dashboard.html"
    if template_path.exists():
        return FileResponse(template_path)
    return HTMLResponse("<h3>CellSentinel Dashboard initializing...</h3>")
