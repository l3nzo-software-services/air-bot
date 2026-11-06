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
from cellsentinel.database import init_db, SessionLocal
from cellsentinel.models import Device, Telemetry
from cellsentinel.schemas import DeviceRegisterRequest
from cellsentinel.services.device_service import register_device
from cellsentinel.services.tower_resolver import resolve_cell_tower
from cellsentinel.api import devices, telemetry, dashboard


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown hooks."""
    # 1. Initialize SQLite schema & load verified local tower fixtures
    init_db()

    # 2. Seed default authorized reference device if table is empty
    with SessionLocal() as db:
        dev_count = db.query(Device).count()
        if dev_count == 0:
            reg_req = DeviceRegisterRequest(
                imei="358941098765432",
                device_name="Google Pixel 8 Pro"
            )
            seeded_dev, seeded_key = register_device(db, reg_req)

            # Seed initial telemetry for Connaught Place reference tower
            resolved = await resolve_cell_tower(db, 404, 45, 1234, 56789)
            initial_telemetry = Telemetry(
                device_id=seeded_dev.id,
                mcc=404,
                mnc=45,
                lac=1234,
                cell_id=56789,
                signal_strength=-72.0,
                latitude=resolved.latitude,
                longitude=resolved.longitude,
                accuracy_radius=resolved.accuracy_radius,
                location_source=resolved.location_source,
                timestamp=seeded_dev.registration_timestamp
            )
            db.add(initial_telemetry)
            seeded_dev.last_seen_timestamp = seeded_dev.registration_timestamp
            db.commit()

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
